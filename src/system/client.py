"""One Gemini client for the process, built on first use. The first use is the expensive one:
the SDK's imports, the client, and the first connection. The imports and the client are the
span client_init; the first connection shows up inside the first embed or generate span."""
from __future__ import annotations

from src.tracing import span

_sdk = None


def get_sdk():
    """-> (client, types): the shared client and the SDK's config types."""
    global _sdk
    if _sdk is None:
        with span("client_init"):
            from google import genai
            from google.genai import types
            _sdk = (genai.Client(), types)   # the client reads GEMINI_API_KEY
    return _sdk
