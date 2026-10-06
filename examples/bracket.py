"""Fillet + chamfer test part with an analytic volume (used by bin/verify):

    V = (X*Y - (4-pi)*r^2) * Z - pi*(d/2)^2 * Z - pi*c^2*(d/2 + c/3)   (= 10634.528 mm^3 by default)

A 40 x 30 x 10 mm block, all four vertical edges filleted r=5, a centred 12 mm through hole with
a 1 mm chamfer on the top edge. Override with -D size_x=…, -D hole_d=… etc.
"""
from build123d import Axis, BuildPart, Box, Cylinder, GeomType, Mode, chamfer, fillet

size_x = globals().get("size_x", 40.0)
size_y = globals().get("size_y", 30.0)
size_z = globals().get("size_z", 10.0)
fillet_r = globals().get("fillet_r", 5.0)
hole_d = globals().get("hole_d", 12.0)
chamfer_c = globals().get("chamfer_c", 1.0)
part = globals().get("part", "bracket")

with BuildPart() as bp:
    Box(size_x, size_y, size_z)
    fillet(bp.edges().filter_by(Axis.Z), radius=fillet_r)
    with BuildPart(mode=Mode.SUBTRACT):
        Cylinder(hole_d / 2, size_z)
    hole_edges = bp.edges().filter_by(GeomType.CIRCLE).filter_by(lambda e: abs(e.radius - hole_d / 2) < 1e-6)
    chamfer(hole_edges.group_by(Axis.Z)[-1], length=chamfer_c)

if part == "fitcheck":
    # A fit check passes when the intersection of two bodies is empty (exit 3).
    result = bp.part - bp.part
else:
    result = bp.part
