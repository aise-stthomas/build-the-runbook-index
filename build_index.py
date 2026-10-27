#!/usr/bin/env python3
"""PART 2 · BUILD THE INDEX: chunk the runbooks, build the lexical index, embed the chunks.

    uv run build_index.py                     # the whole indexing path: chunks → lexical → embeddings → manifest
    uv run build_index.py --max-words 60      # smaller chunks (the chunk-size dial, Part 7)
    uv run build_index.py --skip-embeddings   # rebuild chunks and lexical only; keep the shipped embeddings (no key needed)

Writes data/index/: chunks.jsonl, lexical.json, embeddings.jsonl, query-cache.jsonl, manifest.json.
The embedding step is the only one that calls a model: one batched call per 50 chunks, then one
per labelled question so Part 3 needs no key. Everything else is plain Python.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv  # noqa: E402
from src.index.chunk import chunk_corpus  # noqa: E402
from src.index.lexical import LexicalIndex  # noqa: E402
from src.index import vector as vec  # noqa: E402
from src.harness.qa import load_qa  # noqa: E402

load_dotenv()
ROOT = os.path.dirname(os.path.abspath(__file__))
RUNBOOKS, INDEX = os.path.join(ROOT, "data", "runbooks"), os.path.join(ROOT, "data", "index")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-words", type=int, default=150, help="split a section longer than this at paragraph boundaries")
    ap.add_argument("--skip-embeddings", action="store_true", help="keep the shipped embeddings.jsonl; no model call")
    ap.add_argument("--model", default=vec.DEFAULT_EMBEDDING_MODEL)
    a = ap.parse_args()
    os.makedirs(INDEX, exist_ok=True)

    # ---- step 1: chunk ----------------------------------------------------------------------
    chunks = chunk_corpus(RUNBOOKS, a.max_words)
    with open(os.path.join(INDEX, "chunks.jsonl"), "w") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    docs = {c["doc_id"] for c in chunks}
    print(f"step 1  chunk      {len(docs)} runbooks → {len(chunks)} chunks "
          f"(max {a.max_words} words a section; {sum(c['tokens'] for c in chunks):,} tokens in all)")

    # ---- step 2: the lexical index ------------------------------------------------------------
    lex = LexicalIndex()
    for c in chunks:
        lex.add(c["id"], c["text"])
    lex.save(os.path.join(INDEX, "lexical.json"))
    print(f"step 2  lexical    {len(lex.postings):,} terms, {sum(len(p) for p in lex.postings.values()):,} postings")

    # ---- step 3: the embeddings (THE MODEL CALL) ----------------------------------------------
    emb_path = os.path.join(INDEX, "embeddings.jsonl")
    ids_hash = hashlib.sha256("\n".join(c["id"] + c["text"] for c in chunks).encode()).hexdigest()[:12]
    old = json.load(open(os.path.join(INDEX, "manifest.json"))) if os.path.exists(os.path.join(INDEX, "manifest.json")) else {}
    if a.skip_embeddings:
        if not os.path.exists(emb_path) or old.get("chunks_hash") != ids_hash:
            raise SystemExit("--skip-embeddings: the shipped embeddings do not match these chunks "
                             "(different --max-words, or edited runbooks). Run without the flag.")
        model = old["embedding_model"]
        print(f"step 3  embed      skipped: kept the shipped embeddings ({model})")
        cache = vec.QueryCache(os.path.join(INDEX, "query-cache.jsonl"))
        todo = [q["question"] for q in load_qa() if cache.get(q["question"]) is None]
        if todo and os.environ.get("GEMINI_API_KEY"):
            for q, v in zip(todo, vec.embed(todo, "RETRIEVAL_QUERY", model)):
                cache.put(q, v)
            print(f"step 3b questions  {len(todo)} labelled questions not yet in the query cache: embedded")
        elif todo:
            print(f"step 3b questions  {len(todo)} labelled questions are not in the query cache and there is no key: measure_recall.py will need one")
    else:
        if not os.environ.get("GEMINI_API_KEY"):
            raise SystemExit("step 3 needs GEMINI_API_KEY in .env (or use --skip-embeddings to keep the shipped vectors)")
        model = a.model
        t0 = time.perf_counter()
        vectors = vec.embed([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT", model)
        with open(emb_path, "w") as f:
            for c, v in zip(chunks, vectors):
                f.write(json.dumps({"id": c["id"], "vector": v}) + "\n")
        # the query cache is only valid for the model that built it
        cache_path = os.path.join(INDEX, "query-cache.jsonl")
        if old.get("embedding_model") != model and os.path.exists(cache_path):
            os.remove(cache_path)
        print(f"step 3  embed      {len(vectors)} chunks × {vec.DIMENSIONS} numbers with {model}, "
              f"{len(vectors) // 50 + 1} calls, {time.perf_counter() - t0:.1f} s")

        # ---- step 3b: embed the labelled questions, so Part 3 runs with no key ----------------
        cache = vec.QueryCache(cache_path)
        qa = load_qa()
        todo = [q["question"] for q in qa if cache.get(q["question"]) is None]
        if todo:
            for q, v in zip(todo, vec.embed(todo, "RETRIEVAL_QUERY", model)):
                cache.put(q, v)
        print(f"step 3b questions  {len(qa)} labelled questions embedded into the query cache ({len(todo)} new)")

    # ---- step 4: the manifest: what this index is, pinned ------------------------------------
    manifest = {"built_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "runbooks": len(docs),
                "chunks": len(chunks), "max_words": a.max_words, "chunks_hash": ids_hash,
                "embedding_model": model, "dimensions": vec.DIMENSIONS}
    json.dump(manifest, open(os.path.join(INDEX, "manifest.json"), "w"), indent=2)
    print(f"step 4  manifest   index of {len(chunks)} chunks, embedding model {model}, built {manifest['built_at']}")
    print(f"\nwrote data/index/. Next: uv run measure_recall.py")


if __name__ == "__main__":
    main()
