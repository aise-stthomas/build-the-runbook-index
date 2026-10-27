"""The vector index: one embedding per chunk, and an exact nearest-neighbour search.

The embedding model is the vendor's (Gemini), called once per chunk at build time with the
task type RETRIEVAL_DOCUMENT, and once per question at the request with RETRIEVAL_QUERY.
Vectors are normalized to unit length, so the similarity is a sum of products.

The search is exact: the question's vector against every chunk's vector. A few hundred
chunks times 768 numbers is a few milliseconds in plain Python; an approximate index (the
inverted file from the ranking lecture) only earns its place at millions of chunks, and
its recall is measured against exactly this scan.

A query cache (data/index/query-cache.jsonl) remembers every question embedded, keyed by
the question text, so a question is embedded once, and Part 3 runs with no key at all
when the questions were embedded at build time.
"""
from __future__ import annotations

import json
import logging
import math
import os

logging.getLogger("google_genai.models").setLevel(logging.ERROR)
DEFAULT_EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
DIMENSIONS = 768


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [round(x / n, 6) for x in v]


def embed(texts: list[str], task: str, model: str = DEFAULT_EMBEDDING_MODEL, batch: int = 50) -> list[list[float]]:
    """task: RETRIEVAL_DOCUMENT for chunks, RETRIEVAL_QUERY for questions. Batched; retried on 429."""
    from google import genai
    from google.genai import types
    from src.system.plumbing import with_retries

    client = genai.Client()  # reads GEMINI_API_KEY

    def one_batch(prompt, temperature, model, system=None):
        resp = client.models.embed_content(model=model, contents=prompt,
                                           config=types.EmbedContentConfig(task_type=task, output_dimensionality=DIMENSIONS))
        return [e.values for e in resp.embeddings]

    call = with_retries(one_batch)
    out = []
    for i in range(0, len(texts), batch):
        out.extend(_normalize(v) for v in call(texts[i:i + batch], None, model))
    return out


class QueryCache:
    def __init__(self, path: str):
        self.path, self.rows = path, {}
        if os.path.exists(path):
            for line in open(path):
                r = json.loads(line); self.rows[r["text"]] = r["vector"]

    def get(self, text: str) -> list[float] | None:
        return self.rows.get(text)

    def put(self, text: str, vector: list[float]) -> None:
        self.rows[text] = vector
        try:
            with open(self.path, "a") as f:
                f.write(json.dumps({"text": text, "vector": vector}) + "\n")
        except OSError:
            pass   # a read-only package (Lambda): the cache lives in memory for this sandbox only


def embed_query(text: str, cache: QueryCache | None = None, model: str = DEFAULT_EMBEDDING_MODEL) -> list[float]:
    if cache and (v := cache.get(text)) is not None:
        return v
    v = embed([text], "RETRIEVAL_QUERY", model)[0]
    if cache:
        cache.put(text, v)
    return v


def similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))   # both unit length: the cosine


def search(qvec: list[float], vectors: dict[str, list[float]], k: int = 10) -> list[tuple[str, float]]:
    """Exact nearest neighbours: score every chunk, keep the top k."""
    scored = [(cid, similarity(qvec, v)) for cid, v in vectors.items()]
    return sorted(scored, key=lambda x: -x[1])[:k]
