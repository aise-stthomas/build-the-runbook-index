"""The Lambda entry point: the FastAPI app in app.py, adapted to Lambda's event shape by Mangum.

Run this file directly to exercise exactly that path on your laptop, with no AWS:

    uv run src/function/handler.py                       # one question through the Lambda event shape
    PROVIDER=fake uv run src/function/handler.py         # no key: the model is faked, retrieval is real
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from mangum import Mangum  # noqa: E402
from src.function.app import app  # noqa: E402

handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    body = json.dumps({"message": sys.argv[1] if len(sys.argv) > 1 else "How do I rotate the model key?"})
    headers = {"content-type": "application/json"}
    if os.environ.get("LAB_TOKEN"):
        headers["x-lab-token"] = os.environ["LAB_TOKEN"]
    event = {"version": "2.0", "routeKey": "$default", "rawPath": "/chat", "rawQueryString": "", "headers": headers,
             "requestContext": {"http": {"method": "POST", "path": "/chat", "sourceIp": "127.0.0.1"}},
             "body": body, "isBase64Encoded": False}
    out = handler(event, None)
    print(out["statusCode"])
    print(json.dumps(json.loads(out["body"]), indent=2))
