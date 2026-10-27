#!/usr/bin/env bash
# One question to the deployed chat service, with curl. The URL is public; the token is the key.
#   ./call.sh "How do I rotate the model key?"
#   LAB_URL=https://.../chat LAB_TOKEN=... ./call.sh "..."    a classmate's service, with the token they gave you
#   ./call.sh "..." --raw                                       the whole JSON response
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a
: "${LAB_URL:?run ./deploy.sh first, or set LAB_URL}"
Q="${1:-How do I rotate the model key?}"
BODY="$(python3 -c 'import json,sys; print(json.dumps({"message": sys.argv[1]}))' "$Q")"
RESP="$(curl -s -X POST "$LAB_URL" -H "x-lab-token: ${LAB_TOKEN:-}" -H 'content-type: application/json' -d "$BODY" -w '\n%{http_code} %{time_total}')"
STATUS="$(printf '%s' "$RESP" | tail -n 1)"
JSON="$(printf '%s' "$RESP" | sed '$d')"
if [ "${2:-}" = "--raw" ]; then printf '%s\n' "$JSON" | python3 -m json.tool; echo "$STATUS"; exit 0; fi
printf '%s' "$JSON" | python3 src/function/show.py
echo "http $STATUS s"
