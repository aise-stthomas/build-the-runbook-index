"""Recall at k for a retriever, against the labelled chunk ids, per slice.

recall@k for one question = |relevant ∩ top k| / |relevant|. With one relevant chunk it is
1 or 0: a hit. The rate on a slice is the mean over its questions, reported with its count.
Questions with no answer in the corpus have no recall; for them the measure is whether
the best similarity falls under the floor (the stop rate), reported separately.
"""
from __future__ import annotations

import math

from src.harness.qa import slices


def recall_at_k(relevant: list[str], ranked: list[tuple[str, float]], k: int) -> float:
    top = {cid for cid, _ in ranked[:k]}
    return len(set(relevant) & top) / len(relevant)


def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = x / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def measure(index, qa: list[dict], retrievers: list[str], k: int = 5) -> dict:
    """{retriever: {slice: (hits, n)}} over the answerable questions, plus every question's row."""
    answerable = [q for q in qa if q["in_corpus"]]
    missing = [(q["id"], cid) for q in answerable for cid in q["relevant"] if cid not in index.chunks]
    if missing:
        raise SystemExit("the QA set points at chunk ids that are not in the index (a runbook was edited, or the "
                         "chunking changed): " + ", ".join(f"{q}:{c}" for q, c in missing[:8]) + "\nRebuild the index, or fix data/qa/questions.jsonl.")
    per_q = {r: {} for r in retrievers}
    for r in retrievers:
        for q in answerable:
            per_q[r][q["id"]] = recall_at_k(q["relevant"], index.search(q["question"], r, k), k)
    table = {}
    for r in retrievers:
        table[r] = {}
        for s in ["all"] + slices(answerable):
            qs = answerable if s == "all" else [q for q in answerable if s in q["slices"]]
            if qs:
                table[r][s] = (sum(per_q[r][q["id"]] for q in qs), len(qs))
    return {"table": table, "per_question": per_q}


def print_table(result: dict, k: int) -> None:
    table = result["table"]
    retrievers = list(table)
    slice_names = list(next(iter(table.values())))
    w = max(len(s) for s in slice_names) + 2
    print(f"\nrecall at {k}, per retriever and per slice (hits / questions)\n")
    print("slice".ljust(w) + "".join(r.rjust(22) for r in retrievers))
    for s in slice_names:
        row = s.ljust(w)
        for r in retrievers:
            hits, n = table[r][s]
            lo, hi = wilson(round(hits), n)
            row += f"{hits:5.1f}/{n:<3d} {hits / n * 100:3.0f}% ({lo * 100:.0f}–{hi * 100:.0f})".rjust(22)
        print(row)
    print("\nin parentheses: the 95% interval on the rate. Small slices have wide intervals; that is the point.")
