#!/usr/bin/env python3
"""PART 3 · MEASURE RECALL: each retriever against the labelled QA set, per slice. No model call
for generation; the questions' embeddings come from the query cache built in Part 2.

    uv run measure_recall.py                   # recall at 3 and at 5: lexical, vector, hybrid, per slice
    uv run measure_recall.py --k 1,3,5,10
    uv run measure_recall.py --show            # every question: hit or miss per retriever, and what came back
    uv run measure_recall.py --floor 0.6       # the not-found floor: stop rate on the unanswerable, wrong-stop on the rest
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv  # noqa: E402
from src.harness.qa import load_qa  # noqa: E402
from src.harness.recall import measure, print_table, wilson  # noqa: E402
from src.index.store import Index  # noqa: E402

load_dotenv()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", default="3,5", help="one or more values, comma separated")
    ap.add_argument("--retrievers", default="lexical,vector,hybrid")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--floor", type=float, default=None)
    a = ap.parse_args()
    index = Index()
    qa = load_qa()
    retrievers = a.retrievers.split(",")
    print(f"index: {index.manifest['chunks']} chunks, embedding model {index.embedding_model}, built {index.manifest['built_at']}")
    print(f"QA set: {len(qa)} questions, {sum(q['in_corpus'] for q in qa)} answerable, {sum(not q['in_corpus'] for q in qa)} not in the corpus")

    ks = [int(x) for x in a.k.split(",")]
    for k in ks:
        res = measure(index, qa, retrievers, k)
        print_table(res, k)
    k = ks[-1]

    if a.show:
        print(f"\nper question at k = {k} (1 = every labelled chunk is in the top {k})\n")
        for q in qa:
            if not q["in_corpus"]:
                continue
            marks = "  ".join(f"{r}={int(res['per_question'][r][q['id']])}" for r in retrievers)
            top = [cid for cid, _ in index.search(q["question"], "hybrid", k)]
            print(f"{q['id']}  {marks}   {q['question'][:60]}")
            print(f"       relevant {q['relevant']}   hybrid top {k}: {top}")

    # the floor: the best similarity for every question, answerable or not
    print("\nbest similarity (the vector index's top score), answerable questions against the rest:")
    best = {q["id"]: index.best_similarity(q["question"]) for q in qa}
    for label, rows in (("answerable", [q for q in qa if q["in_corpus"]]), ("not in corpus", [q for q in qa if not q["in_corpus"]])):
        vals = sorted(best[q["id"]] for q in rows)
        print(f"  {label:14s} n={len(vals):2d}  min {vals[0]:.3f}  median {vals[len(vals) // 2]:.3f}  max {vals[-1]:.3f}   "
              + " ".join(f"{v:.2f}" for v in vals))
    if a.floor is not None:
        stop = [q for q in qa if not q["in_corpus"] and best[q["id"]] < a.floor]
        wrong = [q for q in qa if q["in_corpus"] and best[q["id"]] < a.floor]
        n_no, n_yes = sum(not q["in_corpus"] for q in qa), sum(q["in_corpus"] for q in qa)
        lo, hi = wilson(len(stop), n_no); lo2, hi2 = wilson(len(wrong), n_yes)
        print(f"\nfloor {a.floor}: stopped {len(stop)}/{n_no} of the unanswerable ({lo * 100:.0f}–{hi * 100:.0f}%); "
              f"wrongly stopped {len(wrong)}/{n_yes} of the answerable ({lo2 * 100:.0f}–{hi2 * 100:.0f}%)")
        if wrong:
            print("  wrongly stopped: " + ", ".join(q["id"] for q in wrong))


if __name__ == "__main__":
    main()
