"""Print a /chat response for a human: the answer and its sources, or why there is none.
Used by call.sh; reads the JSON body on stdin."""
import json
import sys

raw = sys.stdin.read()
try:
    r = json.loads(raw)
except Exception:
    print(raw)
    sys.exit(0)
if r.get("answer"):
    print(r["answer"])
    print("\nsources:")
    for s in r["sources"]:
        print(f"  [{s['n']}] {s['id']} · {s['title']} › {s['heading']} · as of {s['as_of']}")
elif r.get("not_found"):
    print(f"NOT FOUND (stopped by the {r.get('stopped_by')}). What matched: " + ", ".join(x["id"] for x in r["retrieved"]))
elif r.get("fell_back"):
    print(f"FELL BACK: {r.get('check', '')}. Sources: " + ", ".join(p["id"] for p in r["passages"]))
else:
    print(r.get("detail") or r)
f = r.get("function", {})
if f:
    print(f"\ncold_start={f.get('cold_start')}  init_ms={f.get('init_ms')}  retrieval_ms={r.get('retrieval_ms')}  "
          f"generation_ms={r.get('generation_ms')}  build={f.get('build')}")
