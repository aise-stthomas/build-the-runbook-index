#!/usr/bin/env python3
"""PART 6 · THE JUDGE, step 1: answer every labelled question and save the answers, with the
passages the model saw, so that you and the judge label the same things.

    uv run record_answers.py                 # → data/answers/answers.jsonl, and data/answers/labels.jsonl for you to fill in
    uv run record_answers.py --floor 0.6
    PROVIDER=fake uv run record_answers.py   # plumbing check only; fake answers are not worth labelling
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv  # noqa: E402
from src.assistant.answer import answer  # noqa: E402
from src.harness.qa import load_qa  # noqa: E402
from src.index.store import Index  # noqa: E402

load_dotenv()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answers")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--floor", type=float, default=0.0)
    a = ap.parse_args()
    index, qa = Index(), load_qa()
    os.makedirs(OUT, exist_ok=True)
    answers, labels = [], []
    for q in qa:
        rec = answer(q["question"], index, a.k, a.floor)
        rec["id"], rec["slices"], rec["in_corpus"], rec["reference"] = q["id"], q["slices"], q["in_corpus"], q["reference"]
        rec["passage_texts"] = [{"n": p["n"], "id": p["id"], "text": index.chunks[p["id"]]["text"]} for p in rec["passages"]]
        answers.append(rec)
        state = "NOT_FOUND" if rec["not_found"] else ("fell back" if rec["fell_back"] else "answered")
        print(f"{q['id']}  {state:10s}  {q['question'][:70]}")
        if rec["answer"]:
            labels.append({"id": q["id"], "question": q["question"], "answer": rec["answer"],
                           "passages": [p["id"] for p in rec["passages"]], "grounded": None})
    # the seeded answers: written by hand over real passages, some wrong on purpose, so that the
    # judge is tested on failures as well as on passes. They are labelled and judged like the rest.
    seeded_path = os.path.join(OUT, "seeded.jsonl")
    if os.path.exists(seeded_path):
        for r in (json.loads(l) for l in open(seeded_path)):
            texts = [{"n": i, "id": cid, "text": index.chunks[cid]["text"]} for i, cid in enumerate(r["passages"], 1)]
            answers.append({"id": r["id"], "question": r["question"], "answer": r["answer"], "not_found": False, "fell_back": False,
                            "in_corpus": True, "slices": ["seeded"], "reference": None, "seeded": True,
                            "passages": [{"n": t["n"], "id": t["id"]} for t in texts], "passage_texts": texts})
            labels.append({"id": r["id"], "question": r["question"], "answer": r["answer"], "passages": r["passages"], "grounded": None})
        print(f"\nplus {sum(1 for r in answers if r.get('seeded'))} seeded answers, written by hand; some are wrong on purpose")
    with open(os.path.join(OUT, "answers.jsonl"), "w") as f:
        for r in answers:
            f.write(json.dumps(r) + "\n")
    lp = os.path.join(OUT, "labels.jsonl")
    if os.path.exists(lp):
        print(f"\n{lp} exists; not overwriting your labels. Delete it to start again.")
    else:
        with open(lp, "w") as f:
            for r in labels:
                f.write(json.dumps(r) + "\n")
    print(f"\nwrote data/answers/answers.jsonl ({len(answers)} rows, {len(labels)} answers to label)")
    print("now label them yourself:  uv run label.py      (one at a time: the answer, the passages, yes or no)")
    print("then the judge:           uv run judge.py && uv run validate_judge.py")


if __name__ == "__main__":
    main()
