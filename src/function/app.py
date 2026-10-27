"""PART 4 · THE CHAT SERVICE: the assistant as a web service. One FastAPI app that runs on your
laptop (uvicorn) and on AWS Lambda (through Mangum, see handler.py) without changing a line.

    POST /chat   {"message": "How do I rotate the model key?"}  ->  the answer with its sources,
                 what was retrieved, whether it stopped, every version that touched it
    GET  /       a health check: the index that is loaded, no model call
    GET  /docs   Swagger UI, locally and on the deployed API

The index is loaded once, at import: on Lambda that is part of the cold start, and the
health check reports how long it took. Every question writes one QUESTION line to the log:
what the model saw and said, which is the question log.
"""
from __future__ import annotations

import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_T0 = time.perf_counter()
from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.security import APIKeyHeader  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from src.assistant.answer import DEFAULT_MODEL, answer, question_log_line  # noqa: E402
from src.index.store import Index  # noqa: E402

INDEX = Index()                                        # the cold start includes this
if os.environ.get("GEMINI_API_KEY") and os.environ.get("PROVIDER", "gemini") != "fake":
    from src.system.client import get_sdk
    get_sdk()                                          # and this: the SDK's imports and the client, about 3.5 s on Lambda,
                                                       # paid once at start-up instead of inside the first request
INIT_MS = round((time.perf_counter() - _T0) * 1000)
BUILD = os.environ.get("BUILD", "local")
INVOCATIONS = 0

app = FastAPI(title="runbook-assistant", version="1.0",
              description="A question in, an answer written from the runbooks with its sources out.")
_token_header = APIKeyHeader(name="x-lab-token", auto_error=False, description="the LAB_TOKEN deploy.sh saved in .env")


def check_token(x_lab_token: str | None = Depends(_token_header)) -> None:
    expected = os.environ.get("LAB_TOKEN")
    if expected and x_lab_token != expected:
        raise HTTPException(status_code=401, detail="bad or missing x-lab-token header")


class ChatRequest(BaseModel):
    message: str = Field(..., examples=["The model keeps telling me to slow down. Is it the per-minute limit or the daily one?"])
    k: int = Field(default=5, ge=1, le=10, description="passages given to the model")
    floor: float = Field(default=0.0, ge=0, le=1, description="stop before generation when the best similarity is under this")


def _meta(started: float, cold: bool) -> dict:
    return {"cold_start": cold, "init_ms": INIT_MS, "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "invocation": INVOCATIONS, "model": DEFAULT_MODEL, "build": BUILD,
            "index": {"chunks": INDEX.manifest["chunks"], "embedding_model": INDEX.embedding_model, "built_at": INDEX.manifest["built_at"]}}


@app.get("/")
def health() -> dict:
    global INVOCATIONS
    started = time.perf_counter(); cold = INVOCATIONS == 0; INVOCATIONS += 1
    return {"ok": True, "function": _meta(started, cold)}


@app.post("/chat")
def chat(req: ChatRequest, _: None = Depends(check_token)) -> dict:
    """One question, one answer with its sources. No memory between calls."""
    global INVOCATIONS
    started = time.perf_counter(); cold = INVOCATIONS == 0; INVOCATIONS += 1
    try:
        rec = answer(req.message, INDEX, req.k, req.floor)
    except SystemExit as e:                     # the plumbing gave up: a daily cap, a dead provider
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}"[:300])
    print(question_log_line(rec))
    rec.pop("draft", None)
    rec["function"] = _meta(started, cold)
    return rec
