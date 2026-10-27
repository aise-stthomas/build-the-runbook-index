#!/usr/bin/env python3
"""PART 6 · THE JUDGE, step 2: the judge reads every recorded answer with its passages and says
whether it is grounded. Three runs by default, so the judge's own noise is visible.

    uv run judge.py              # → data/answers/judge.jsonl: one line per answer with the verdicts of every run
    uv run judge.py --runs 1
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv  # noqa: E402
from src.harness.judge import JUDGE_MODEL, judge  # noqa: E402

load_dotenv()
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answers")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    answers = [json.loads(l) for l in open(os.path.join(OUT, "answers.jsonl"))]
    answered = [r for r in answers if r.get("answer")]
    print(f"judging {len(answered)} answers × {a.runs} runs with {JUDGE_MODEL}\n")
    rows = []
    for r in answered:
        verdicts = [judge(r["answer"], r["passage_texts"]) for _ in range(a.runs)]
        rows.append({"id": r["id"], "verdicts": verdicts, "judge_model": JUDGE_MODEL})
        flag = "" if len(set(verdicts)) == 1 else "   ← flipped between runs"
        print(f"{r['id']}  {' '.join(f'{v:3s}' for v in verdicts)}{flag}")
    with open(os.path.join(OUT, "judge.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    flips = sum(1 for row in rows if len(set(row["verdicts"])) > 1)
    print(f"\nwrote data/answers/judge.jsonl. verdicts that flipped across runs: {flips}/{len(rows)}"
          + (f" = {flips / len(rows) * 100:.0f}%: the judge's own noise floor" if rows else ""))
    print("next: uv run validate_judge.py   (after you have filled in data/answers/labels.jsonl)")


if __name__ == "__main__":
    main()
