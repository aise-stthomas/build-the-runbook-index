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
printf '%s' "$JSON" | python3 -c '
import json, sys
try:
    r = json.load(sys.stdin)
except Exception:
    print(sys.stdin.read()); sys.exit(0)
if r.get("answer"):
    print(r["answer"]); print("\nsources:")
    for s in r["sources"]:
        print(f"  [{s[\"n\"]}] {s[\"id\"]} · {s[\"title\"]} › {s[\"heading\"]} · as of {s[\"as_of\"]}")
elif r.get("not_found"):
    print("NOT FOUND (stopped by the " + str(r.get("stopped_by")) + "). What matched: " + ", ".join(x["id"] for x in r["retrieved"]))
elif r.get("fell_back"):
    print("FELL BACK: " + r.get("check", "") + ". Sources: " + ", ".join(p["id"] for p in r["passages"]))
else:
    print(r.get("detail") or r)
f = r.get("function", {})
if f:
    print(f"\ncold_start={f.get(\"cold_start\")}  init_ms={f.get(\"init_ms\")}  retrieval_ms={r.get(\"retrieval_ms\")}  generation_ms={r.get(\"generation_ms\")}  build={f.get(\"build\")}")
'
echo "http $STATUS s"
