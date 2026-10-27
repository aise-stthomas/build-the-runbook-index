#!/usr/bin/env python3
"""PART 6 · THE JUDGE, step 3: your labels against the judge's. The four counts, sensitivity
(failures it caught), specificity, raw agreement, κ with its interval; the judge's own noise
across runs; the corrected groundedness rate. Plus the code checks that need no judge: did
the system say NOT_FOUND on the unanswerable questions, and not on the others.

    uv run validate_judge.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.harness.agreement import corrected_rate, four_counts  # noqa: E402
from src.harness.recall import wilson  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "answers")


def pct(x, n):
    lo, hi = wilson(x, n)
    return f"{x}/{n} = {x / n * 100:.0f}% ({lo * 100:.0f}–{hi * 100:.0f})" if n else "n/a"


def main() -> None:
    answers = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(OUT, "answers.jsonl")))}
    labels = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(OUT, "labels.jsonl")))}
    judged = {r["id"]: r for r in (json.loads(l) for l in open(os.path.join(OUT, "judge.jsonl")))}

    # ---- the code checks: NOT_FOUND where it should be, and not where it should not ----------
    system_rows = [r for r in answers.values() if not r.get("seeded")]
    unans = [r for r in system_rows if not r["in_corpus"]]
    ans = [r for r in system_rows if r["in_corpus"]]
    print("the code checks (no judge needed)")
    print(f"  stopped on the unanswerable:      {pct(sum(r['not_found'] for r in unans), len(unans))}"
          + ("   ← these answered when nothing in the corpus answers: " + ", ".join(r["id"] for r in unans if not r["not_found"]) if any(not r["not_found"] for r in unans) else ""))
    print(f"  wrongly stopped, answerable:      {pct(sum(r['not_found'] for r in ans), len(ans))}")
    print(f"  fell back (draft failed a check): {pct(sum(r['fell_back'] for r in system_rows), len(system_rows))}")

    # ---- your labels ------------------------------------------------------------------------
    yours = {i: (r["grounded"] or "").lower() for i, r in labels.items()}
    missing = [i for i, v in yours.items() if v not in ("yes", "no")]
    if missing:
        print(f"\n{len(missing)} answers in labels.jsonl have no label yet ({', '.join(missing[:6])}{'…' if len(missing) > 6 else ''}); "
              f"they are left out. Fill in \"grounded\" and run this again.")
    yours = {i: v for i, v in yours.items() if v in ("yes", "no")}
    if not yours:
        raise SystemExit("\nno labels yet: fill in data/answers/labels.jsonl first")
    print(f"\nyour labels: {len(yours)} answers, {sum(v == 'no' for v in yours.values())} marked not grounded")

    # ---- the judge's reliability ------------------------------------------------------------
    runs = max(len(r["verdicts"]) for r in judged.values())
    flips = sum(1 for r in judged.values() if len(set(r["verdicts"])) > 1)
    print(f"\nthe judge against itself: {runs} runs; verdicts that flipped: {pct(flips, len(judged))}  (its own noise floor)")

    # ---- the judge against you --------------------------------------------------------------
    first = {i: r["verdicts"][0] for i, r in judged.items()}
    c = four_counts(yours, first, positive="no")
    print(f"\nthe judge (run 1) against your labels, on {c['n']} answers")
    print(f"                         judge: not grounded   judge: grounded")
    print(f"  you: not grounded       {c['both_fail']:^18d} {c['missed']:^16d}")
    print(f"  you: grounded           {c['false_alarm']:^18d} {c['both_pass']:^16d}")
    sens = c["sensitivity"]; spec = c["specificity"]
    print(f"\n  sensitivity (failures it caught)  {pct(c['both_fail'], c['both_fail'] + c['missed'])}")
    print(f"  specificity (passes it passed)    {pct(c['both_pass'], c['both_pass'] + c['false_alarm'])}")
    print(f"  raw agreement                     {pct(c['both_fail'] + c['both_pass'], c['n'])}")
    if c.get("kappa") is not None:
        print(f"  κ = {c['kappa']:.2f}  (interval {c['kappa_low']:.2f} to {c['kappa_high']:.2f})")
    if c["both_fail"] + c["missed"] == 0:
        print("\n  you marked no answer as ungrounded, so sensitivity cannot be measured: the judge was never tested on a failure.")
        print("  That is the usual state of a judge nobody has validated. Add harder questions, or label more answers.")

    # ---- the rate the judge reports, and what it is worth -------------------------------------
    n_j = len(first); unsupported = sum(v == "no" for v in first.values())
    reported = unsupported / n_j if n_j else 0
    print(f"\nthe judge's own rate: {pct(unsupported, n_j)} of answers not grounded")
    if sens is not None and spec is not None and sens > (1 - spec):
        p = corrected_rate(reported, sens, spec)
        print(f"  corrected for the judge's error rates (Rogan–Gladen): about {p * 100:.0f}%")
    disagree = [i for i in yours if first.get(i) and first[i] != yours[i]]
    if disagree:
        print(f"\nread every disagreement; the pattern is what to write into the rubric:")
        for i in disagree:
            print(f"  {i}: you {yours[i]}, judge {first[i]}   {labels[i]['answer'][:90]}")


if __name__ == "__main__":
    main()
