"""Convert a model file to another format (STEP -> STL/3MF/OBJ/PLY/PNG, mesh -> mesh/PNG)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import EXIT_OK, empty, fail, parser, write_meta  # noqa: E402
import exporters  # noqa: E402
import loaders  # noqa: E402


def main() -> int:
    p = parser("convert a model file")
    p.add_argument("--input", required=True)
    a = p.parse_args()
    try:
        obj = loaders.load(a.input)
    except Exception as e:  # noqa: BLE001
        return fail(a.meta, f"cannot read input: {type(e).__name__}: {e}")
    if exporters.is_empty(obj):
        return empty(a.meta)
    try:
        m = exporters.metrics(obj)
        exporters.export(obj, a.format, a.out)
    except exporters.Unsupported as e:
        return fail(a.meta, str(e))
    write_meta(a.meta, ok=True, empty=False, warnings=[], **m)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
