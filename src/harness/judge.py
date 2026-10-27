"""The judge: a second model call that reads an answer and the passages it was given and
says whether the answer is grounded in them. One verdict per answer (the lecture's
per-claim version is the same call with more rows).

It is a model: it has an error rate, it drifts, and it is validated against people
(validate_judge.py) before its rate counts for anything.
"""
from __future__ import annotations

import logging
import os
import re

logging.getLogger("google_genai.models").setLevel(logging.ERROR)
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"))

RUBRIC = """You are checking whether an answer is grounded in the passages it was written from.
Answer yes if every factual statement in the answer is stated by, or directly follows from, the passages.
Answer no if any statement is not in the passages, contradicts them, or leaves out a condition the passages attach (an exception, a limit, a time).
Judge only what is in the passages; whether the statement is true elsewhere does not matter.
Reply with one word: yes or no."""


def judge(answer_text: str, passages: list[dict], model: str = JUDGE_MODEL, provider: str | None = None) -> str:
    provider = provider or os.environ.get("PROVIDER", "gemini")
    if provider == "fake":
        return "yes"
    from google import genai
    from google.genai import types
    from src.system.plumbing import with_retries

    client = genai.Client()
    body = "PASSAGES\n\n" + "\n".join(f"[{p['n']}] {p['id']}\n{p['text']}\n" for p in passages) + f"\nANSWER\n{answer_text}"

    def sample(prompt, temperature, model, system=None):
        cfg = types.GenerateContentConfig(system_instruction=system, temperature=temperature, max_output_tokens=10)
        return (client.models.generate_content(model=model, contents=prompt, config=cfg).text or "").strip()

    raw = with_retries(sample)(body, 0.0, model, RUBRIC)
    m = re.match(r"\s*(yes|no)\b", raw.lower())
    return m.group(1) if m else f"unparsed:{raw[:30]}"
