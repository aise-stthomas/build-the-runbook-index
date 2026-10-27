"""Chunking: a runbook becomes the passages the index returns and the model reads.

A runbook is Markdown: a title line, a metadata line, then sections under `## ` headings.
One section is one chunk, with the runbook's title and the heading prepended, so the
heading path travels with the text. A section longer than the cap is split at paragraph
boundaries into RB-04#2.1, RB-04#2.2, ...  (the chunk-size dial, Part 7).

A chunk carries: its id, the runbook id and title, the heading, the text the index and the
model see, an approximate token count, the owner and the as-of date from the metadata line.
"""
from __future__ import annotations

import glob
import os
import re


def parse_runbook(path: str) -> dict:
    lines = open(path, encoding="utf-8").read().splitlines()
    title_line = next(l for l in lines if l.startswith("# "))
    m = re.match(r"# (RB-\d+) · (.+)", title_line)
    doc_id, title = m.group(1), m.group(2).strip()
    meta = {"owner": "", "as_of": "", "readers": ""}
    for l in lines:
        if l.startswith("owner:"):   # owner: platform team · as of 2026-10-19 · readers: everyone
            for part in l.split("·"):
                part = part.strip()
                if part.startswith("owner:"):
                    meta["owner"] = part[len("owner:"):].strip()
                elif part.startswith("as of"):
                    meta["as_of"] = part[len("as of"):].strip()
                elif part.startswith("readers:"):
                    meta["readers"] = part[len("readers:"):].strip()
            break
    sections, heading, body = [], None, []
    for l in lines:
        if l.startswith("# ") or l.startswith("owner:"):
            continue
        if l.startswith("## "):
            if heading is not None:
                sections.append((heading, "\n".join(body).strip()))
            heading, body = l[3:].strip(), []
        elif heading is not None:
            body.append(l)
    if heading is not None:
        sections.append((heading, "\n".join(body).strip()))
    return {"doc_id": doc_id, "title": title, **meta, "sections": sections}


def _split(body: str, max_words: int) -> list[str]:
    """Split a section at paragraph boundaries so that no piece exceeds max_words
    (a paragraph longer than the cap stays whole; a sentence is never cut)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces, cur = [], []
    for p in paras:
        if cur and len(" ".join(cur + [p]).split()) > max_words:
            pieces.append("\n\n".join(cur)); cur = []
        cur.append(p)
    if cur:
        pieces.append("\n\n".join(cur))
    return pieces


def chunk_runbook(rb: dict, max_words: int = 150) -> list[dict]:
    out = []
    for i, (heading, body) in enumerate(rb["sections"], start=1):
        pieces = _split(body, max_words)
        for j, piece in enumerate(pieces, start=1):
            cid = f"{rb['doc_id']}#{i}" if len(pieces) == 1 else f"{rb['doc_id']}#{i}.{j}"
            text = f"{rb['title']} › {heading}\n{piece}"
            out.append({"id": cid, "doc_id": rb["doc_id"], "title": rb["title"], "heading": heading,
                        "text": text, "tokens": int(len(text.split()) * 1.3),
                        "owner": rb["owner"], "as_of": rb["as_of"], "readers": rb["readers"]})
    return out


def chunk_corpus(runbook_dir: str, max_words: int = 150) -> list[dict]:
    chunks = []
    for path in sorted(glob.glob(os.path.join(runbook_dir, "RB-*.md"))):
        chunks.extend(chunk_runbook(parse_runbook(path), max_words))
    return chunks
