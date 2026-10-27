#!/usr/bin/env python3
"""PART 5 · the traces of the deployed service, read back from its log. Every call wrote one
QUESTION line with its spans; this prints each as the tree a trace viewer would draw.

    uv run traces.py                  # the last 30 minutes
    uv run traces.py --since 2h
    uv run traces.py --request-id ID  # one call, by the id on its START and REPORT lines
    uv run traces.py --local FILE     # a file of QUESTION lines (e.g. saved from ask.py output)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.tracing import render  # noqa: E402

FN = os.environ.get("FUNCTION_NAME", "runbook-assistant")


def question_lines(since: str, request_id: str | None) -> list[str]:
    cmd = ["aws", "logs", "tail", f"/aws/lambda/{FN}", "--since", since, "--region", "us-east-1", "--format", "short"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(out.stderr.strip() or "aws logs tail failed: is the Learner Lab session live?")
    lines = []
    keep = request_id is None
    for line in out.stdout.splitlines():
        if request_id:
            if f"START RequestId: {request_id}" in line:
                keep = True
            elif line.split(" ", 1)[-1].startswith("START RequestId:"):
                keep = False
        if keep and "QUESTION {" in line:
            lines.append(line)
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="30m")
    ap.add_argument("--request-id", default=None)
    ap.add_argument("--local", default=None)
    a = ap.parse_args()
    lines = [l for l in open(a.local) if "QUESTION {" in l] if a.local else question_lines(a.since, a.request_id)
    if not lines:
        print("no QUESTION lines found; make a call, wait a few seconds, run it again")
        return
    for line in lines:
        stamp, _, rest = line.partition(" ")
        rec = json.loads(rest.split("QUESTION ", 1)[1])
        state = "NOT_FOUND" if rec.get("not_found") else ("fell back" if rec.get("fell_back") else "answered")
        print(f"\n{stamp}  {rec['question'][:80]}   [{state}, {rec.get('total_ms')} ms]")
        print(render(rec.get("spans", []), rec.get("total_ms")))


if __name__ == "__main__":
    main()
