"""The lexical index: an inverted index over the chunks' terms, scored with BM25.

Build: every chunk is tokenized; for every term, the list of chunks that contain it and
how often (the posting list). Search: the question's terms select a few posting lists;
the chunks on them are scored and the top k returned. Nothing else is read.

BM25 in words: rare terms count more (a term in 3 chunks of 2,000,000 outweighs one in
half of them); repeated terms count more, but saturate; long chunks are discounted.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict

from src.tracing import traced

STOP = set("a an the of to in on for and or is are was were be been it this that with as at by from "
           "do does did not no yes if then than so into your you we our its their what how when which who".split())
_TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")   # keeps err-4032, x-lab-token, run_batch.py, us-east-1 whole


def tokenize(text: str) -> list[str]:
    """Lower-case; split on anything but letters, digits and the joiners inside identifiers;
    drop stop words; strip a plural s. Deliberately simple: the point is that the same
    function runs at build time and at the request, so a term matches itself."""
    out = []
    for t in _TOKEN.findall(text.lower()):
        t = t.rstrip(".")
        if t in STOP or len(t) < 2:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


class LexicalIndex:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.postings: dict[str, dict[str, int]] = defaultdict(dict)   # term -> {chunk id: term count}
        self.length: dict[str, int] = {}                                # chunk id -> terms in the chunk
        self.k1, self.b = k1, b

    def add(self, chunk_id: str, text: str) -> None:
        terms = tokenize(text)
        self.length[chunk_id] = len(terms)
        for t, n in Counter(terms).items():
            self.postings[t][chunk_id] = n

    @property
    def n_chunks(self) -> int:
        return len(self.length)

    def idf(self, term: str) -> float:
        n_t = len(self.postings.get(term, {}))
        return math.log((self.n_chunks - n_t + 0.5) / (n_t + 0.5) + 1)

    @traced("lexical")
    def search(self, question: str, k: int = 10) -> list[tuple[str, float]]:
        avg = sum(self.length.values()) / max(1, self.n_chunks)
        scores: dict[str, float] = defaultdict(float)
        for term in set(tokenize(question)):
            idf = self.idf(term)
            for cid, f in self.postings.get(term, {}).items():       # one posting list per query term
                denom = f + self.k1 * (1 - self.b + self.b * self.length[cid] / avg)
                scores[cid] += idf * f * (self.k1 + 1) / denom
        return sorted(scores.items(), key=lambda x: -x[1])[:k]

    def save(self, path: str) -> None:
        json.dump({"k1": self.k1, "b": self.b, "length": self.length, "postings": self.postings}, open(path, "w"))

    @classmethod
    def load(cls, path: str) -> "LexicalIndex":
        d = json.load(open(path))
        ix = cls(d["k1"], d["b"])
        ix.length = d["length"]
        ix.postings = defaultdict(dict, d["postings"])
        return ix
