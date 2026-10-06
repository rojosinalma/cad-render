"""Repair a mesh: merge vertices, drop degenerate/duplicate faces, fix winding and normals, fill
holes, then run it through manifold3d. STEP input is tessellated first. Reports what changed in
``warnings`` and whether the result is watertight."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from common import EXIT_OK, empty, fail, log, parser, write_meta  # noqa: E402
import exporters  # noqa: E402
import loaders  # noqa: E402


def manifold_pass(mesh: trimesh.Trimesh) -> trimesh.Trimesh | None:
    try:
        import manifold3d as m3d
    except ImportError:
        return None
    mm = m3d.Mesh(vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
                  tri_verts=np.asarray(mesh.faces, dtype=np.uint32))
    man = m3d.Manifold(mm)
    if man.is_empty():
        return None
    out = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(out.vert_properties[:, :3], dtype=float),
                           faces=np.asarray(out.tri_verts, dtype=np.int64), process=False)


def main() -> int:
    p = parser("repair a mesh")
    p.add_argument("--input", required=True)
    a = p.parse_args()
    try:
        obj = loaders.load(a.input)
        mesh = exporters.as_mesh(obj)
    except Exception as e:  # noqa: BLE001
        return fail(a.meta, f"cannot read input: {type(e).__name__}: {e}")
    if len(mesh.faces) == 0:
        return empty(a.meta)

    notes: list[str] = []
    before = {"faces": len(mesh.faces), "watertight": bool(mesh.is_watertight), "winding": bool(mesh.is_winding_consistent)}
    log("repair", f"before: {before}")
    mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces, process=True, validate=True)
    if len(mesh.faces) != before["faces"]:
        notes.append(f"removed {before['faces'] - len(mesh.faces)} degenerate/duplicate faces")
    if not before["winding"]:
        trimesh.repair.fix_winding(mesh)
        notes.append("fixed face winding")
    trimesh.repair.fix_normals(mesh)
    if not mesh.is_watertight:
        filled = trimesh.repair.fill_holes(mesh)
        notes.append("filled holes" if filled else "holes remain (could not fill)")
    manifold = manifold_pass(mesh)
    if manifold is not None and len(manifold.faces) > 0:
        if manifold.is_watertight and not mesh.is_watertight:
            notes.append("manifold3d produced a watertight mesh")
        mesh = manifold if manifold.is_watertight or not mesh.is_watertight else mesh
    else:
        notes.append("manifold3d could not build a manifold; kept trimesh result")
    if not mesh.is_watertight:
        notes.append("result is NOT watertight")
    log("repair", f"after: faces={len(mesh.faces)} watertight={mesh.is_watertight} notes={notes}")
    try:
        m = exporters.metrics(mesh)
        exporters.export(mesh, a.format, a.out)
    except exporters.Unsupported as e:
        return fail(a.meta, str(e))
    write_meta(a.meta, ok=True, empty=False, warnings=notes, watertight=bool(mesh.is_watertight),
               faces=len(mesh.faces), **m)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
