"""Shared loaders: a file on disk -> B-rep (STEP) or trimesh (mesh formats)."""

from __future__ import annotations

import os

import trimesh

from common import log

BREP_EXT = {"step", "stp"}
MESH_EXT = {"stl", "3mf", "obj", "ply", "off"}


def load(path: str):
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if ext in BREP_EXT:
        from build123d import import_step

        log("load", f"STEP {path}")
        return import_step(path)
    if ext in MESH_EXT:
        log("load", f"mesh {path}")
        obj = trimesh.load(path, force="mesh")
        if isinstance(obj, trimesh.Scene):
            obj = trimesh.util.concatenate(tuple(obj.dump()))
        return obj
    raise ValueError(f"unsupported input .{ext}")
