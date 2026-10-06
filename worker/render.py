"""Render a build123d script.

The script runs as a module with ``-D name=value`` pairs injected as globals first. It must leave a
``result`` at module level (a build123d Part/Compound/Shape, a BuildPart builder, or a
trimesh.Trimesh) or define ``build()`` returning one. Empty geometry exits 3.
"""

from __future__ import annotations

import ast
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import EXIT_OK, empty, fail, log, parser, write_meta  # noqa: E402
import exporters  # noqa: E402


def parse_define(raw: str) -> tuple[str, object]:
    name, _, value = raw.partition("=")
    name = name.strip()
    if not name.isidentifier():
        raise ValueError(f"bad define name {name!r}")
    try:
        return name, ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return name, value  # bare word -> string, e.g. part=fitcheck


def unwrap(obj):
    """Builders (BuildPart/BuildSketch) expose the shape as .part/.sketch/.line; use it."""
    for attr in ("part", "sketch", "line"):
        inner = getattr(obj, attr, None)
        if inner is not None and exporters.is_brep(inner):
            return inner
    return obj


def main() -> int:
    p = parser("render a build123d script")
    p.add_argument("--main", required=True)
    p.add_argument("-D", action="append", default=[], metavar="NAME=VALUE")
    a = p.parse_args()

    init_globals: dict[str, object] = {"__name__": "__cad__"}
    try:
        for raw in a.D:
            k, v = parse_define(raw)
            init_globals[k] = v
            log("render", f"define {k}={v!r}")
    except ValueError as e:
        return fail(a.meta, str(e))

    script_dir = os.path.dirname(os.path.abspath(a.main))
    sys.path.insert(0, script_dir)
    os.chdir(script_dir)
    log("render", f"exec {a.main}")
    try:
        ns = runpy.run_path(a.main, init_globals=init_globals, run_name="__cad__")
    except SystemExit as e:
        return fail(a.meta, f"script called exit({e.code})")
    except Exception as e:  # noqa: BLE001 - user script, report whatever it raised
        import traceback

        traceback.print_exc()
        return fail(a.meta, f"{type(e).__name__}: {e}")

    result = ns.get("result")
    if result is None and callable(ns.get("build")):
        try:
            result = ns["build"]()
        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            return fail(a.meta, f"build() raised {type(e).__name__}: {e}")
    if result is None:
        return fail(a.meta, "script defines neither `result` nor `build()`")
    result = unwrap(result)

    warnings = list(ns.get("warnings", [])) if isinstance(ns.get("warnings"), (list, tuple)) else []
    if exporters.is_empty(result):
        return empty(a.meta, warnings=warnings)

    try:
        m = exporters.metrics(result)
        exporters.export(result, a.format, a.out)
    except exporters.Unsupported as e:
        return fail(a.meta, str(e), warnings=warnings)
    write_meta(a.meta, ok=True, empty=False, warnings=warnings, **m)
    log("render", f"volume={m['volume_mm3']} bbox={m['bbox']}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
