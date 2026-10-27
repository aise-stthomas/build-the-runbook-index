"""The assistant: retrieve, assemble the context, generate, check, cite.

    answer(question, index) -> {"answer", "not_found", "sources", "passages", "citations", ...}

Retrieve: the hybrid top k passages. Assemble: the instructions, the passages with ids,
the question. Generate: one model call. Check, in code: every [n] is among the passages
given, or the draft is not shown and the passages are returned instead. Cite: the sources
are built by code from the chunk ids; the model never writes a link.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time

from dotenv import load_dotenv

from src.index.store import Index
from src.tracing import render, trace, traced

load_dotenv()
logging.getLogger("google_genai.models").setLevel(logging.ERROR)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
NOT_FOUND = "NOT_FOUND"

INSTRUCTIONS = """You answer questions from the engineers who run a support-ticket system, using only the runbook passages below.
Rules:
1. Use only the passages. Do not use any other knowledge, even if you are sure of it.
2. Every sentence that states a fact ends with the passage it came from, as [n].
3. Quote the number and the condition: a limit, a time, a command, an exception.
4. If the passages do not answer the question, reply with exactly NOT_FOUND and nothing else.
5. At most four sentences."""


@traced("assemble")
def build_context(question: str, passages: list[dict]) -> tuple[str, str]:
    """(system instruction, user text): what the model receives, and nothing else."""
    lines = []
    for i, p in enumerate(passages, start=1):
        lines.append(f"[{i}] {p['id']} · {p['title']} · {p['heading']} · as of {p['as_of']}\n{p['text']}\n")
    user = "PASSAGES\n\n" + "\n".join(lines) + f"\nQUESTION\n{question}"
    return INSTRUCTIONS, user


@traced("generate")
def generate(system: str, user: str, model: str = DEFAULT_MODEL, provider: str | None = None) -> str:
    provider = provider or os.environ.get("PROVIDER", "gemini")
    if provider == "fake":
        return f"(fake provider) The first passage says something about this [1]."
    from src.system.client import get_sdk
    from src.system.plumbing import with_retries

    client, types = get_sdk()

    def sample(prompt, temperature, model, system=None):
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=temperature, max_output_tokens=400)
        return (client.models.generate_content(model=model, contents=prompt, config=cfg).text or "").strip()

    return with_retries(sample)(user, 0.0, model, system)


_CITE = re.compile(r"\[(\d+)\]")


@traced("check")
def check(draft: str, n_passages: int) -> dict:
    """The code checks: NOT_FOUND, or a draft whose every citation is a passage it was given."""
    if NOT_FOUND in draft:   # the contract says NOT_FOUND alone; a draft that says it anywhere is a not-found
        extra = draft.replace(NOT_FOUND, "").strip()
        return {"not_found": True, "ok": True, "citations": [],
                "reason": "model said NOT_FOUND" + (" (and wrote text around it, which is not shown)" if extra else "")}
    cites = sorted({int(n) for n in _CITE.findall(draft)})
    bad = [n for n in cites if n < 1 or n > n_passages]
    if not cites:
        return {"not_found": False, "ok": False, "citations": [], "reason": "no citations in the draft"}
    if bad:
        return {"not_found": False, "ok": False, "citations": cites, "reason": f"citations not among the passages: {bad}"}
    if len(draft.split()) > 140:
        return {"not_found": False, "ok": False, "citations": cites, "reason": "over the length limit"}
    return {"not_found": False, "ok": True, "citations": cites, "reason": ""}


def answer(question: str, index: Index, k: int = 5, floor: float = 0.0, retriever: str = "hybrid",
           model: str = DEFAULT_MODEL, provider: str | None = None) -> dict:
    """The request path, as one trace: every stage is a span, and the spans go out with the answer."""
    with trace("chat") as tr:
        out = _answer(question, index, k, floor, retriever, model, provider)
    out["spans"] = tr.rows()
    out["total_ms"] = tr.total_ms
    return out


def _answer(question: str, index: Index, k: int, floor: float, retriever: str, model: str, provider: str | None) -> dict:
    t0 = time.perf_counter()
    hits = index.search(question, retriever, k)
    passages = [index.chunks[cid] for cid, _ in hits]
    best = index.best_similarity(question) if (floor > 0 or retriever != "lexical") else None
    retrieval_ms = round((time.perf_counter() - t0) * 1000)
    out = {"question": question, "retriever": retriever, "k": k,
           "retrieved": [{"id": cid, "score": round(s, 4)} for cid, s in hits], "best_similarity": best,
           "passages": [{"n": i, "id": p["id"], "title": p["title"], "heading": p["heading"]} for i, p in enumerate(passages, 1)],
           "model": model, "index_version": index.manifest.get("built_at"), "embedding_model": index.embedding_model,
           "retrieval_ms": retrieval_ms}
    if floor > 0 and best is not None and best < floor:
        out.update({"answer": None, "not_found": True, "stopped_by": "floor", "citations": [], "sources": [],
                    "generation_ms": 0, "fell_back": False})
        return out
    system, user = build_context(question, passages)
    out["context_sha"] = hashlib.sha256((system + user).encode()).hexdigest()[:12]
    out["context_tokens"] = int(len((system + user).split()) * 1.3)
    t1 = time.perf_counter()
    draft = generate(system, user, model, provider)
    out["generation_ms"] = round((time.perf_counter() - t1) * 1000)
    chk = check(draft, len(passages))
    out["draft"] = draft
    out["not_found"] = chk["not_found"]
    out["stopped_by"] = "model" if chk["not_found"] else None
    out["citations"] = chk["citations"]
    out["check"] = chk["reason"]
    out["fell_back"] = not chk["ok"]
    out["answer"] = None if (chk["not_found"] or not chk["ok"]) else draft
    out["sources"] = [{"n": n, "id": passages[n - 1]["id"], "title": passages[n - 1]["title"],
                       "heading": passages[n - 1]["heading"], "as_of": passages[n - 1]["as_of"],
                       "file": f"data/runbooks/{passages[n - 1]['doc_id']}.md"} for n in chk["citations"]]
    return out


def question_log_line(rec: dict) -> str:
    """One line per question, what the model saw and said: the question log."""
    keep = {k: rec.get(k) for k in ("question", "retriever", "k", "retrieved", "best_similarity", "context_sha",
                                   "context_tokens", "answer", "not_found", "stopped_by", "citations", "check",
                                   "fell_back", "model", "embedding_model", "index_version", "retrieval_ms", "generation_ms",
                                   "total_ms", "spans")}
    return "QUESTION " + json.dumps(keep)


def render_trace(rec: dict) -> str:
    return render(rec.get("spans", []), rec.get("total_ms"))
