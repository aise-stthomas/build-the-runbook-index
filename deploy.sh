#!/usr/bin/env bash
# PART 5 · DEPLOY: the chat service as a function with an HTTP API in front of it, in the AWS Academy Learner Lab.
#
#   ./deploy.sh                      build the package (code + the index), create or update the function and the API, print the URL
#   ./deploy.sh --timeout 30         the function's time limit in seconds (default 30)
#   ./deploy.sh --memory 1024        more memory, which on Lambda is also more CPU
#
# What it assumes: the AWS CLI with a live Learner Lab session pasted into ~/.aws/credentials
# (Configuring AWS, section 3), uv, your Gemini key in .env, and data/index/ built (Part 2).
# It uses the pre-created LabRole, never creates IAM anything, and stays in us-east-1.
set -euo pipefail
cd "$(dirname "$0")"

FN="${FUNCTION_NAME:-runbook-assistant}"
API="${API_NAME:-runbook-assistant}"
export AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""
TIMEOUT=30; MEMORY=512
while [ $# -gt 0 ]; do
  case "$1" in
    --timeout)  TIMEOUT="$2"; shift 2 ;;
    --memory)   MEMORY="$2"; shift 2 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done

command -v aws >/dev/null || { echo "aws CLI not found: brew install awscli (or see Configuring AWS)"; exit 1; }
command -v uv  >/dev/null || { echo "uv not found: see the README"; exit 1; }
[ -f .env ] || { echo "no .env: cp .env.example .env and paste your Gemini key"; exit 1; }
[ -f data/index/manifest.json ] || { echo "no index: run  uv run build_index.py  first (Part 2)"; exit 1; }
set -a; . ./.env; set +a
: "${GEMINI_API_KEY:?GEMINI_API_KEY is not set in .env}"
if [ -z "${LAB_TOKEN:-}" ]; then
  LAB_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  printf '\nLAB_TOKEN=%s\n' "$LAB_TOKEN" >> .env
  echo "made a LAB_TOKEN and saved it in .env (POST /chat checks it on every request; GET / is open)"
fi

ACCOUNT="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || { echo "aws sts get-caller-identity failed: start a Learner Lab session and paste fresh credentials"; exit 1; }
ROLE="arn:aws:iam::${ACCOUNT}:role/LabRole"
BUILD="$(date -u +%Y-%m-%d.%H%M)"
ENV_VARS="Variables={GEMINI_API_KEY=${GEMINI_API_KEY},LAB_TOKEN=${LAB_TOKEN},BUILD=${BUILD},GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.1-flash-lite},EMBEDDING_MODEL=${EMBEDDING_MODEL:-gemini-embedding-001}}"

# --- build: the dependencies for Lambda's Linux, the code, and the index as data ---------
echo "building the package..."
rm -rf build && mkdir -p build/pkg
uv pip install --quiet --target build/pkg \
  --python-platform x86_64-manylinux_2_28 --python-version 3.12 \
  "google-genai>=1.0" "python-dotenv>=1.0" "fastapi>=0.115" "mangum>=0.17"
cp -R src build/pkg/src
mkdir -p build/pkg/data/index
cp data/index/chunks.jsonl data/index/lexical.json data/index/embeddings.jsonl data/index/manifest.json build/pkg/data/index/
[ -f data/index/query-cache.jsonl ] && cp data/index/query-cache.jsonl build/pkg/data/index/
find build/pkg -name "__pycache__" -type d -prune -exec rm -rf {} +
( cd build/pkg && zip -qr ../function.zip . -x '*.pyc' -x '*/__pycache__/*' )
echo "  $(du -h build/function.zip | cut -f1) zipped, $(du -sh build/pkg | cut -f1) unpacked (the index is $(du -sh data/index | cut -f1) of it)"

# --- the function: create or update ----------------------------------------------------
if aws lambda get-function --function-name "$FN" >/dev/null 2>&1; then
  echo "updating the function $FN..."
  aws lambda update-function-code --function-name "$FN" --zip-file "fileb://build/function.zip" >/dev/null
  aws lambda wait function-updated --function-name "$FN"
  aws lambda update-function-configuration --function-name "$FN" --handler src.function.handler.handler \
    --runtime python3.12 --timeout "$TIMEOUT" --memory-size "$MEMORY" --environment "$ENV_VARS" >/dev/null
  aws lambda wait function-updated --function-name "$FN"
else
  echo "creating the function $FN as $ROLE..."
  aws lambda create-function --function-name "$FN" \
    --runtime python3.12 --architectures x86_64 --handler src.function.handler.handler \
    --role "$ROLE" --zip-file "fileb://build/function.zip" \
    --timeout "$TIMEOUT" --memory-size "$MEMORY" --environment "$ENV_VARS" >/dev/null
  aws lambda wait function-active --function-name "$FN"
fi
FN_ARN="$(aws lambda get-function --function-name "$FN" --query Configuration.FunctionArn --output text)"

# --- the API: an HTTP API in front of the function, public; the function checks the token --
ID="$(aws apigatewayv2 get-apis --query "Items[?Name=='${API}'].ApiId | [0]" --output text 2>/dev/null)"
if [ -z "$ID" ] || [ "$ID" = "None" ]; then
  echo "creating the API $API..."
  ID="$(aws apigatewayv2 create-api --name "$API" --protocol-type HTTP --target "$FN_ARN" --query ApiId --output text)"
else
  echo "the API $API exists ($ID); keeping it"
fi
URL="$(aws apigatewayv2 get-api --api-id "$ID" --query ApiEndpoint --output text)"
aws lambda add-permission --function-name "$FN" --statement-id "apigw-${ID}" --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:us-east-1:${ACCOUNT}:${ID}/*" >/dev/null 2>&1 || true

if grep -q '^LAB_URL=' .env; then
  sed -i.bak "s|^LAB_URL=.*|LAB_URL=${URL}/chat|" .env && rm -f .env.bak
else
  printf 'LAB_URL=%s\n' "${URL}/chat" >> .env
fi

echo
echo "deployed: $FN   build $BUILD   timeout ${TIMEOUT}s   memory ${MEMORY} MB   behind the API $API ($ID)"
echo "url:      ${URL}/chat   (saved to .env as LAB_URL)"
echo "docs:     ${URL}/docs   open to anyone: Authorize with your LAB_TOKEN, then POST /chat"
echo
echo "try it:   ./call.sh \"How do I rotate the model key?\""
echo "logs:     aws logs tail /aws/lambda/$FN --follow --region us-east-1     (the QUESTION lines are the question log)"
