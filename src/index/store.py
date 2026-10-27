"""Loading the built index from data/index/: the chunks, the lexical index, the vectors and
the manifest that pins the embedding model they were made with."""
from __future__ import annotations

import json
import os

from src.index.hybrid import rrf
from src.index.lexical import LexicalIndex
from src.index import vector as vec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INDEX_DIR = os.path.join(ROOT, "data", "index")


class Index:
    def __init__(self, index_dir: str = INDEX_DIR):
        self.dir = index_dir
        self.manifest = json.load(open(os.path.join(index_dir, "manifest.json")))
        self.chunks = {c["id"]: c for c in (json.loads(l) for l in open(os.path.join(index_dir, "chunks.jsonl")))}
        self.lexical = LexicalIndex.load(os.path.join(index_dir, "lexical.json"))
        self.vectors = {}
        p = os.path.join(index_dir, "embeddings.jsonl")
        if os.path.exists(p):
            for line in open(p):
                r = json.loads(line); self.vectors[r["id"]] = r["vector"]
        self.cache = vec.QueryCache(os.path.join(index_dir, "query-cache.jsonl"))
        self.embedding_model = self.manifest.get("embedding_model")

    def search_lexical(self, q: str, k: int = 10): return self.lexical.search(q, k)

    def search_vector(self, q: str, k: int = 10):
        if not self.vectors:
            raise SystemExit("no embeddings in the index: run build_index.py (Part 2)")
        return vec.search(vec.embed_query(q, self.cache, self.embedding_model), self.vectors, k)

    def search_hybrid(self, q: str, k: int = 10, depth: int = 20):
        return rrf([self.search_lexical(q, depth), self.search_vector(q, depth)], k)

    def search(self, q: str, retriever: str = "hybrid", k: int = 10):
        return {"lexical": self.search_lexical, "vector": self.search_vector, "hybrid": self.search_hybrid}[retriever](q, k)

    def best_similarity(self, q: str) -> float:
        """The best cosine between the question and any chunk: what the not-found floor is set on."""
        return self.search_vector(q, 1)[0][1]
