"""
Terminal progress logging. Long stages (model loads, PubMed calls, ASR/OCR,
LLM generation) can silently take a minute or more — without visible
progress that reads as "hung." Every stage that can block for more than a
second or two should call step()/done() around it.
"""
import sys
import time

_start = time.monotonic()


def _elapsed() -> str:
    return f"{time.monotonic() - _start:6.1f}s"


def step(msg: str):
    print(f"[{_elapsed()}] -> {msg}", file=sys.stderr, flush=True)


def done(msg: str):
    print(f"[{_elapsed()}]    {msg}", file=sys.stderr, flush=True)
