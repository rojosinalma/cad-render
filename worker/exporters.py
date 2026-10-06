"""Format registry: output format -> exporter.

Geometry arrives either as a build123d/OCP B-rep (``Shape``) or as a ``trimesh.Trimesh``. Each
exporter takes whichever it supports and writes ``path``. Adding a format = one function + one
line in EXPORTERS.
"""

from __future__ import annotations

import io
import math

import numpy as np
import trimesh

from common import log

TESSELLATION_TOLERANCE = 0.01  # mm, linear deflection for B-rep -> mesh
TESSELLATION_ANGULAR = 0.2  # rad


class Unsupported(Exception):
    pass


# --- geometry helpers --------------------------------------------------------------------------

def is_brep(obj) -> bool:
    return hasattr(obj, "wrapped") and hasattr(obj, "tessellate")


def brep_to_mesh(shape) -> trimesh.Trimesh:
    verts, tris = shape.tessellate(TESSELLATION_TOLERANCE, TESSELLATION_ANGULAR)
    v = np.array([(p.X, p.Y, p.Z) for p in verts], dtype=float)
    f = np.array(tris, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=True)
    mesh.fix_normals()
    return mesh


def as_mesh(obj) -> trimesh.Trimesh:
    if isinstance(obj, trimesh.Trimesh):
        return obj
    if isinstance(obj, trimesh.Scene):
        return obj.to_mesh() if hasattr(obj, "to_mesh") else trimesh.util.concatenate(tuple(obj.dump()))
    if is_brep(obj):
        return brep_to_mesh(obj)
    raise Unsupported(f"cannot mesh a {type(obj).__name__}")


def metrics(obj) -> dict:
    """Volume (mm^3) and bbox [xmin,ymin,zmin,xmax,ymax,zmax] for either geometry kind."""
    if is_brep(obj):
        bb = obj.bounding_box()
        vol = float(obj.volume)
        bbox = [bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z]
    else:
        mesh = as_mesh(obj)
        vol = float(mesh.volume) if mesh.is_watertight else float(abs(mesh.volume))
        bbox = [*mesh.bounds[0], *mesh.bounds[1]]
    return {"volume_mm3": round(vol, 3), "bbox": [round(float(x), 4) for x in bbox]}


def is_empty(obj) -> bool:
    if obj is None:
        return True
    if is_brep(obj):
        try:
            return obj.wrapped is None or obj.volume < 1e-9 and len(obj.faces()) == 0
        except Exception:  # noqa: BLE001 - OCP raises on null shapes
            return True
    mesh = as_mesh(obj)
    return len(mesh.faces) == 0


# --- exporters ---------------------------------------------------------------------------------

def export_stl(obj, path: str) -> None:
    if is_brep(obj):
        from build123d import export_stl as b3d_export_stl

        b3d_export_stl(obj, path, tolerance=TESSELLATION_TOLERANCE, angular_tolerance=TESSELLATION_ANGULAR)
    else:
        as_mesh(obj).export(path, file_type="stl")


def export_step(obj, path: str) -> None:
    if not is_brep(obj):
        raise Unsupported("STEP needs B-rep geometry; a mesh (STL/3MF/OBJ) cannot be converted to STEP")
    from build123d import export_step as b3d_export_step

    b3d_export_step(obj, path)


def export_3mf(obj, path: str) -> None:
    as_mesh(obj).export(path, file_type="3mf")


def export_obj(obj, path: str) -> None:
    as_mesh(obj).export(path, file_type="obj")


def export_ply(obj, path: str) -> None:
    as_mesh(obj).export(path, file_type="ply")


def export_png(obj, path: str, size: int = 1200) -> None:
    """Software-rendered isometric preview (matplotlib Agg): no display, no GPU."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mesh = as_mesh(obj)
    tris = mesh.vertices[mesh.faces]
    normals = mesh.face_normals
    light = np.array([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    shade = np.clip(normals @ light, 0, 1) * 0.65 + 0.35
    base = np.array([0.74, 0.58, 0.98])  # dracula purple
    colors = np.clip(base * shade[:, None], 0, 1)

    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100, facecolor="#282a36")
    ax = fig.add_subplot(111, projection="3d", facecolor="#282a36")
    coll = Poly3DCollection(tris, facecolors=colors, edgecolors=colors, linewidths=0.3, antialiaseds=False)
    ax.add_collection3d(coll)
    lo, hi = mesh.bounds
    centre = (lo + hi) / 2
    half = float(np.max(hi - lo)) / 2 or 1.0
    ax.set_xlim(centre[0] - half, centre[0] + half)
    ax.set_ylim(centre[1] - half, centre[1] + half)
    ax.set_zlim(centre[2] - half, centre[2] + half)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=math.degrees(math.atan(1 / math.sqrt(2))), azim=-45)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#282a36")
    plt.close(fig)
    with open(path, "wb") as f:
        f.write(buf.getvalue())


EXPORTERS = {
    "stl": export_stl,
    "step": export_step,
    "3mf": export_3mf,
    "obj": export_obj,
    "ply": export_ply,
    "png": export_png,
}


def export(obj, fmt: str, path: str) -> None:
    try:
        fn = EXPORTERS[fmt]
    except KeyError:
        raise Unsupported(f"no exporter for {fmt!r} ({', '.join(EXPORTERS)})") from None
    log("export", f"{fmt} -> {path}")
    fn(obj, path)
