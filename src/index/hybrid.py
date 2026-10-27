"""Hybrid retrieval: both indexes, merged by reciprocal rank fusion.

fused(c) = sum over lists of 1 / (60 + rank of c in that list). The two scores (BM25 and a
cosine) are never on the same scale, so the merge uses the two orders and nothing else.
"""
from __future__ import annotations


def rrf(lists: list[list[tuple[str, float]]], k: int = 10, c: int = 60) -> list[tuple[str, float]]:
    fused: dict[str, float] = {}
    for ranked in lists:
        for rank, (cid, _) in enumerate(ranked, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (c + rank)
    return sorted(fused.items(), key=lambda x: -x[1])[:k]
