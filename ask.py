#!/usr/bin/env python3
"""PART 4 · THE CHAT SERVICE, from the terminal: one question through the assistant.

    uv run ask.py "How do I rotate the model key?"
    uv run ask.py "..." --k 3 --retriever lexical
    uv run ask.py "..." --floor 0.6                 # stop before generation when nothing is similar enough
    uv run ask.py "..." --show-context              # print exactly what the model received
    PROVIDER=fake uv run ask.py "..."               # no key: retrieval runs, the model is faked
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv  # noqa: E402
from src.assistant.answer import answer, build_context, question_log_line  # noqa: E402
from src.index.store import Index  # noqa: E402

load_dotenv()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--retriever", default="hybrid", choices=["lexical", "vector", "hybrid"])
    ap.add_argument("--floor", type=float, default=0.0)
    ap.add_argument("--show-context", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    index = Index()
    rec = answer(a.question, index, a.k, a.floor, a.retriever)
    if a.json:
        print(json.dumps(rec, indent=2)); return
    if a.show_context:
        system, user = build_context(a.question, [index.chunks[p["id"]] for p in rec["passages"]])
        print("── SYSTEM INSTRUCTION ──\n" + system + "\n\n── USER TEXT ──\n" + user + "\n── end of context ──\n")
    print(f"retrieved ({a.retriever}, top {a.k}, {rec['retrieval_ms']} ms): " + ", ".join(f"{r['id']} {r['score']:.3f}" for r in rec["retrieved"]))
    if rec.get("best_similarity") is not None:
        print(f"best similarity: {rec['best_similarity']:.3f}" + (f"  (floor {a.floor})" if a.floor else ""))
    print()
    if rec["not_found"]:
        print(f"NOT FOUND  (stopped by the {rec['stopped_by']}). The passages above are what matched; no answer was generated." if rec["stopped_by"] == "floor"
              else "NOT FOUND  (the model said NOT_FOUND). The passages above are what matched.")
    elif rec["fell_back"]:
        print(f"FELL BACK: the draft failed the check ({rec['check']}); showing the sources instead.\n  draft was: {rec['draft'][:200]}")
    else:
        print(rec["answer"])
        print("\nsources:")
        for s in rec["sources"]:
            print(f"  [{s['n']}] {s['id']} · {s['title']} › {s['heading']} · as of {s['as_of']} · {s['file']}")
    print(f"\n{rec['generation_ms']} ms generation · model {rec['model']} · index {rec['index_version']}")
    print(question_log_line(rec))


if __name__ == "__main__":
    main()
