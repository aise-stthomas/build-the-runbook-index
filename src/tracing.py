"""One trace per request, written by the function itself: a list of spans, each with a name,
a start offset, a duration and its parent. The smallest form of the trace-store component.

How it is used, in three lines:

    with trace("chat") as tr:          # the root: opens a trace for everything inside this block
        ...
    tr.rows()                          # the spans, as a list of dicts, for the response and the log

    @traced("vector_scan")             # a decorated function becomes one span, every time it runs
    def search(...): ...

    with span("client_init"):          # an inline block becomes one span
        ...

Outside a trace the decorator and the block cost nothing and change nothing: the harness
calls the same functions with no trace open. Nesting follows the call stack, so the tree
printed by `render()` is the call tree. Nothing here knows about AWS; the same rows would
feed X-Ray, OpenTelemetry or any trace store in an account that has one.
"""
from __future__ import annotations

import contextvars
import functools
import time
from contextlib import contextmanager

_current: contextvars.ContextVar["Trace | None"] = contextvars.ContextVar("trace", default=None)


class Trace:
    def __init__(self, name: str):
        self.name = name
        self.t0 = time.perf_counter()
        self.spans: list[dict] = []
        self._open: list[dict] = []          # the stack of spans not yet finished: the parent chain

    def begin(self, name: str, **attrs) -> dict:
        s = {"name": name, "start_ms": round((time.perf_counter() - self.t0) * 1000, 1), "duration_ms": None,
             "parent": self._open[-1]["name"] if self._open else None, **attrs}
        self.spans.append(s)
        self._open.append(s)
        return s

    def end(self, s: dict) -> None:
        s["duration_ms"] = round((time.perf_counter() - self.t0) * 1000 - s["start_ms"], 1)
        if self._open and self._open[-1] is s:
            self._open.pop()

    def rows(self) -> list[dict]:
        return [dict(s) for s in self.spans]

    @property
    def total_ms(self) -> float:
        return round((time.perf_counter() - self.t0) * 1000, 1)


@contextmanager
def trace(name: str):
    """Open a trace; everything spanned inside the block belongs to it."""
    tr = Trace(name)
    token = _current.set(tr)
    try:
        yield tr
    finally:
        _current.reset(token)


def current() -> Trace | None:
    return _current.get()


@contextmanager
def span(name: str, **attrs):
    """One span around a block. A no-op when no trace is open."""
    tr = _current.get()
    if tr is None:
        yield None
        return
    s = tr.begin(name, **attrs)
    try:
        yield s
    finally:
        tr.end(s)


def traced(name: str | None = None):
    """Decorator: the function becomes one span, named after itself unless told otherwise."""
    def decorate(fn):
        label = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with span(label):
                return fn(*args, **kwargs)
        return wrapper
    return decorate


def render(rows: list[dict], total_ms: float | None = None) -> str:
    """The spans as a tree with a bar per span, scaled to the trace: what a trace viewer draws."""
    if not rows:
        return "(no spans)"
    end = total_ms or max((s["start_ms"] + (s["duration_ms"] or 0)) for s in rows)
    width = 40
    depth = {}
    for s in rows:
        depth[s["name"]] = depth.get(s["parent"], -1) + 1 if s["parent"] else 0
    lines = []
    for s in rows:
        d = s["duration_ms"] or 0
        a = int(s["start_ms"] / end * width) if end else 0
        b = max(a + 1, int((s["start_ms"] + d) / end * width)) if end else a + 1
        bar = " " * a + "█" * (b - a)
        extra = " ".join(f"{k}={v}" for k, v in s.items() if k not in ("name", "start_ms", "duration_ms", "parent"))
        lines.append(f"{'  ' * depth[s['name']] + s['name']:<22s} {s['start_ms']:7.1f} {d:8.1f} ms  |{bar:<{width}}|  {extra}")
    head = f"{'span':<22s} {'start':>7s} {'duration':>11s}  |{'0':<{width}}|{end:.0f} ms"
    return head + "\n" + "\n".join(lines)
