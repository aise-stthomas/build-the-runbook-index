"""The labelled QA set: data/qa/questions.jsonl. One row per question: the question, its
slices, the chunk ids that answer it (empty when the answer is not in the corpus), and the
reference answer (NOT_FOUND when it is not)."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QA_PATH = os.path.join(ROOT, "data", "qa", "questions.jsonl")


def load_qa(path: str = QA_PATH) -> list[dict]:
    rows = [json.loads(l) for l in open(path) if l.strip() and not l.startswith("#")]
    for r in rows:
        r.setdefault("relevant", [])
        r["in_corpus"] = bool(r["relevant"])
    return rows


def slices(rows: list[dict]) -> list[str]:
    seen = []
    for r in rows:
        for s in r["slices"]:
            if s not in seen:
                seen.append(s)
    return seen
