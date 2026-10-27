#!/usr/bin/env python3
"""PART 6 · THE JUDGE, step 1b: label the recorded answers yourself, one at a time. For each
answer you see the question, the answer, and the passages the model was given, and you say
whether every factual statement in the answer is supported by those passages.

    uv run label.py              # walks through every unlabelled answer; saves after each
    uv run label.py --redo q15   # relabel one
    uv run label.py --show       # print the labels so far
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answers")
RULE = ("yes = every factual statement in the answer is stated by, or follows directly from, the passages\n"
        "no  = a statement is not in the passages, contradicts them, or drops a condition they attach (an exception, a limit, a time)\n"
        "Judge only against the passages. Whether a statement is true elsewhere does not matter.")


def save(labels: list[dict]) -> None:
    with open(os.path.join(OUT, "labels.jsonl"), "w") as f:
        for r in labels:
            f.write(json.dumps(r) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redo", default=None)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    answers = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(OUT, "answers.jsonl")))}
    labels = [json.loads(l) for l in open(os.path.join(OUT, "labels.jsonl"))]
    if a.show:
        for r in labels:
            print(f"{r['id']}  {str(r['grounded']):5s}  {r['answer'][:90]}")
        return
    todo = [r for r in labels if r["grounded"] is None or r["id"] == a.redo]
    if not todo:
        print("every answer is labelled. --redo q07 to change one; validate_judge.py to compare with the judge.")
        return
    print(f"{len(todo)} answers to label. The rule:\n{RULE}\n")
    for r in todo:
        rec = answers[r["id"]]
        print("=" * 100)
        print(f"{r['id']}  QUESTION: {r['question']}\n")
        print("ANSWER:\n" + textwrap.fill(r["answer"], 96) + "\n")
        print("THE PASSAGES IT WAS GIVEN:")
        for p in rec["passage_texts"]:
            print(f"  [{p['n']}] {p['id']}")
            print(textwrap.indent(textwrap.fill(p["text"], 92), "      "))
        while True:
            v = input("\ngrounded? [y]es / [n]o / [s]kip / [q]uit: ").strip().lower()
            if v in ("y", "n", "s", "q"):
                break
        if v == "q":
            break
        if v == "s":
            continue
        r["grounded"] = "yes" if v == "y" else "no"
        save(labels)
    done = sum(r["grounded"] is not None for r in labels)
    print(f"\nsaved: {done}/{len(labels)} labelled, {sum(r['grounded'] == 'no' for r in labels)} not grounded. Next: uv run judge.py && uv run validate_judge.py")


if __name__ == "__main__":
    main()
