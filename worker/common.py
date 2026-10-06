"""Shared plumbing for the worker scripts.

Every worker is a subprocess started by lib/worker.rb with --out, --meta and --format; it writes
the result file to --out and a JSON summary to --meta. Exit codes: 0 ok, 3 empty geometry,
1 failure (the "error" key in the meta file carries the reason).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_EMPTY = 3

_T0 = time.monotonic()


def log(subsystem: str, msg: str) -> None:
    print(f"[{subsystem}] {msg}", file=sys.stderr, flush=True)


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--out", required=True)
    p.add_argument("--meta", required=True)
    p.add_argument("--format", required=True)
    return p


def write_meta(path: str, **data) -> None:
    data.setdefault("seconds", round(time.monotonic() - _T0, 2))
    with open(path, "w") as f:
        json.dump(data, f)


def fail(meta_path: str, error: str, **extra) -> int:
    log("worker", f"error: {error}")
    write_meta(meta_path, ok=False, error=error, **extra)
    return EXIT_FAIL


def empty(meta_path: str, **extra) -> int:
    log("worker", "result is empty")
    write_meta(meta_path, ok=True, empty=True, **extra)
    return EXIT_EMPTY


def bbox_list(lo, hi) -> list[float]:
    return [round(float(v), 4) for v in (*lo, *hi)]
