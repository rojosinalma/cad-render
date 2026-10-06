"""Boot-time probe: prints one JSON line with the worker toolchain versions (or ok=false)."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys

info = {"ok": True, "python": platform.python_version()}
try:
    import build123d, trimesh  # noqa: E401
    import OCP  # noqa: F401
    import manifold3d  # noqa: F401

    info["build123d"] = build123d.__version__
    info["trimesh"] = trimesh.__version__
    info["ocp"] = getattr(OCP, "__version__", "?")
    info["manifold3d"] = getattr(manifold3d, "__version__", "?")
except Exception as e:  # noqa: BLE001
    info = {"ok": False, "error": f"{type(e).__name__}: {e}"}
zoo = shutil.which("zoo")
if zoo:
    try:
        info["zoo_cli"] = subprocess.run([zoo, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:  # noqa: BLE001
        info["zoo_cli"] = f"error: {e}"
else:
    info["zoo_cli"] = None
print(json.dumps(info))
sys.exit(0 if info["ok"] else 1)
