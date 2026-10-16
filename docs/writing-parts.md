# Writing parts

A part is a plain Python file executed by the worker (build123d, trimesh and numpy are available).
It must leave a `result` at module level — a build123d `Part`/`Compound`/`Shape`, a `BuildPart`
builder, or a `trimesh.Trimesh` — or define `build()` returning one.

- `-D name=value` pairs become module globals before the script runs. Values go through
  `ast.literal_eval`, so `-D size_x=42` is a float/int and `-D part=fitcheck` stays a string. Read them
  with `globals().get("name", default)` so the script also runs standalone.
- The script's directory is sent as a tarball, so sibling modules and data files import normally.
- Empty geometry exits `3` and writes nothing: `result = a - b` is a fit check that passes when the
  two bodies do not intersect.
- An optional module-level `warnings` list is reported back in `X-Cad-Warnings` / the JSON.

## Reference part

`examples/bracket.py` — a 40 × 30 × 10 mm block with filleted edges and a chamfered through hole,
whose analytic volume `bin/verify` checks against the render:

```python
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

result = bp.part - bp.part if part == "fitcheck" else bp.part   # fit check -> empty -> exit 3
```

```sh
cad-render examples/bracket.py -o bracket.step -D hole_d=8 -D fillet_r=3
cad-render examples/bracket.py -o /dev/null -D part=fitcheck; echo $?   # 3
```

## Multi-file projects

Keep helpers next to the main script and import them as usual; the CLI tars the script's directory
(or `--root DIR`) and the service extracts it into the job's work dir. Over the raw API, send the
archive as `project=@dir.tgz` with `main=<path.py>`; when the archive has exactly one top-level `.py`,
`main` may be omitted.
