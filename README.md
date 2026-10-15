# cad-render

Headless B-rep CAD as an HTTP service: turn [build123d](https://build123d.readthedocs.io) scripts into
STL / STEP / 3MF / PNG, convert and repair meshes, and generate CAD from a text prompt — built for
agents and scripts, one Docker container, file in / file out.

![cad-render demo](docs/demo.png)

## What it does

- **Real B-rep, not CSG meshes.** Parts are modelled in Python with build123d on OpenCascade, so fillets, chamfers and threads are exact, and STEP goes in and out.
- **Mesh tooling.** Convert between STEP / STL / 3MF / OBJ / PLY (plus PNG previews) and repair broken meshes (merge, fill holes, re-orient, manifold pass) until they are watertight.
- **Text-to-CAD.** `POST /zoo` sends a prompt to [Zoo](https://zoo.dev), gets KCL back and exports it to STEP/STL/… — optional, needs a Zoo token.
- **Agent-friendly contract.** Stateless, one request = one file; results come back with `X-Cad-*` headers (volume, bbox, warnings, seconds) or as JSON with the worker log; distinct exit codes in the CLI (`3` = empty geometry, which makes fit checks a one-liner).
- **Print-shop hand-off.** The CLI can upload the result to a [Bambuddy](https://github.com/maziggy/bambuddy) library and run a slicer pipeline in the same command.

## Quick start

```sh
git clone https://github.com/rojosinalma/cad-render.git
cd cad-render
cp .env.example .env            # add ZOO_API_TOKEN only if you want /zoo
docker compose up -d            # pulls ghcr.io/rojosinalma/cad-render:latest (x86_64)
curl http://localhost:9292/health
bin/cad-render examples/bracket.py -o bracket.stl
```

`bin/cad-render` needs `bash`, `curl`, `tar` and `ruby` on the client. Put it on your `PATH` and set
`CAD_RENDER_URL` if the service runs elsewhere.

Prebuilt images: `ghcr.io/rojosinalma/cad-render:<version>` and `:latest` (pin with `CAD_IMAGE_TAG` in
`.env`). To build locally instead — other architectures, or after editing the `Dockerfile` — run
`docker compose up -d --build` (the first build takes a few minutes for the OCP / build123d wheels).

## CLI

```
cad-render [render] <part.py> -o <out.{stl,step,3mf,png}> [-D name=value]... [--root DIR]
cad-render convert  <in.{step,stl,3mf,obj,ply}> -o <out.{stl,step,3mf,obj,ply,png}>
cad-render repair   <in.{stl,3mf,obj,ply,step}> [-o <out>]          # default: <in>.repaired.<ext>
cad-render zoo      "<prompt>" -o <out.{step,stl,3mf,obj,ply,glb,kcl}>   # also writes <out>.kcl
```

| Option | Meaning |
|---|---|
| `-D name=value` | Define a module global before the script runs (repeatable; `-Dname=value` works too). |
| `--root DIR` | Directory sent as the project tarball (default: the script's directory). |
| `--log` | Print the worker log to stderr. |
| `--to-bb` | Upload the result to the Bambuddy library (`BAMBUDDY_URL` + `BAMBUDDY_API_KEY` required). |
| `--folder <name>` | Bambuddy library folder, matched by name (default: library root). |
| `--pipeline "<name>"` | Bambuddy slicer pipeline, matched by name, run on the uploaded file. |
| `--copies N` | Copies for the pipeline run (default 1). |
| `--dry-run` | With `--to-bb`: check auth, resolve folder and pipeline, upload nothing. |

| Exit | Meaning |
|---|---|
| `0` | OK, file written |
| `1` | Render/convert/repair failure or unreachable service |
| `2` | Usage error |
| `3` | Empty geometry — nothing written (a fit check passed) |
| `4` | Zoo failure |
| `5` | Bambuddy upload or pipeline failure (the local file is kept) |

> **A Bambuddy pipeline run slices *and* may enqueue a print on the target printer.** If an agent
> drives `--to-bb --pipeline`, make sure a human approved that exact job first.

## Writing parts

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

## HTTP API

| Route | Input | Output |
|---|---|---|
| `POST /render` | multipart: `project=@dir.tgz` + `main=<path.py>` **or** `file=@part.py` **or** `source=<python>`; `format=stl\|step\|3mf\|png` (default `stl`); `D[]=name=value` (repeatable) or `defines=<JSON object>`; `log=1` | file |
| `POST /convert` | multipart: `file=@model.{step,stp,stl,3mf,obj,ply,off}`; `format=stl\|step\|3mf\|obj\|ply\|png` (default `stl`); `log=1` | file |
| `POST /repair` | multipart: `file=@model.{stl,3mf,obj,ply,off,step,stp}`; optional `format=stl\|3mf\|obj\|ply` (default: the input's format, `stl` for STEP); `log=1` | file |
| `POST /zoo` | JSON `{"prompt": "...", "format": "step\|stl\|3mf\|obj\|ply\|glb\|kcl", "log": 1}` (default `step`, prompt ≤ 4000 chars) | file |
| `GET /health` | — | JSON: `ok`, `version`, toolchain versions, `zoo_token` (bool), `queue{running,waiting}` |
| `GET /` | — | JSON: version and registered ops |

Mesh → STEP is refused (`422`): STEP needs B-rep geometry. A `project` archive is tar/tgz; absolute
paths, `..`, links and device nodes are rejected; when the archive has exactly one top-level `.py`,
`main` may be omitted.

**Response headers** (file responses): `X-Cad-Version`, `X-Cad-Empty` (`0`/`1`), `X-Cad-Warnings`
(count), `X-Cad-Seconds`, `X-Cad-Volume-mm3`, `X-Cad-Bbox` (`xmin,ymin,zmin,xmax,ymax,zmax`),
`X-Cad-Zoo-Id` (`/zoo` only), `X-Cad-Timeout: 1` on a 504. An empty result is a `200` with
`X-Cad-Empty: 1` and an empty body.

**`log=1`** returns JSON instead of the file: `{ok, message, empty, warnings, seconds, exit_code,
volume_mm3, bbox, format, bytes, log, output_base64}` plus `zoo_id`, `zoo_conversation_id` and `kcl`
for `/zoo`. Errors are always JSON `{ok: false, message, ..., log}`.

| Status | When |
|---|---|
| `200` | Done (check `X-Cad-Empty`) |
| `422` | Bad input: unknown format, invalid archive, script error, Zoo not configured, worker failure |
| `503` | Queue full (`CAD_MAX_JOBS` running and `CAD_MAX_QUEUE` waiting) or worker toolchain unavailable (`/health`) |
| `504` | Worker killed after `CAD_TIMEOUT_S` (`ZOO_TIMEOUT_S` + 30 s for `/zoo`) |

```sh
curl -F file=@examples/bracket.py -F format=step -D - -o bracket.step http://localhost:9292/render
curl -F file=@broken.stl http://localhost:9292/repair -o fixed.stl
curl -H 'Content-Type: application/json' -d '{"prompt":"a 20 mm cube with a 5 mm through hole","format":"stl"}' \
     http://localhost:9292/zoo -o cube.stl
```

## Configuration

Everything is an environment variable with a generic default. Secrets go in `.env` (loaded by the app
with dotenv), never in `compose.yaml` `environment:`.

**Service** (`lib/config.rb`)

| Variable | Default | Meaning |
|---|---|---|
| `CAD_TIMEOUT_S` | `300` | Hard timeout per render/convert/repair job; the worker process group is killed |
| `CAD_MAX_JOBS` | `2` | Concurrent worker subprocesses |
| `CAD_MAX_QUEUE` | `8` | Requests allowed to wait for a slot; beyond that `503` |
| `CAD_MAX_UPLOAD_MB` | `100` | Max upload size (file or project archive) |
| `CAD_MAX_FILES` | `2000` | Max entries in a project archive |
| `CAD_PYTHON` | `python3` | Python interpreter for the workers |
| `ZOO_API_TOKEN` | — | Zoo API token; without it `/zoo` answers `422` |
| `ZOO_API_URL` | `https://api.zoo.dev` | Zoo API base (websocket derived from it) |
| `ZOO_POLL_S` | `5` | Copilot websocket ping interval (seconds) |
| `ZOO_TIMEOUT_S` | `600` | Timeout for one text-to-CAD run |

**Compose** (`compose.yaml`)

| Variable | Default | Meaning |
|---|---|---|
| `CAD_PORT` | `9292` | Host port |
| `CAD_IMAGE_TAG` | `latest` | Tag of `ghcr.io/rojosinalma/cad-render` to pull |
| `CAD_UID` / `CAD_GID` | `1000` / `1000` | Container user — match the owner of the checkout so `.env` (0600) is readable |
| `TZ` | `UTC` | Container time zone (log timestamps) |

**CLI** (`bin/cad-render`)

| Variable | Default | Meaning |
|---|---|---|
| `CAD_RENDER_URL` | `http://localhost:9292` | Service base URL |
| `CAD_RENDER_TIMEOUT` | `900` | curl `--max-time` per request (seconds) |
| `BAMBUDDY_URL` | — | Bambuddy base URL, required for `--to-bb` |
| `BAMBUDDY_API_KEY` | — | Bambuddy API key, required for `--to-bb` |

## Security

**Scripts are arbitrary Python executed inside the container, and there is no authentication.**
Run cad-render only on a trusted network for trusted clients (your own tools and agents), or put it
behind a reverse proxy that authenticates. The container is hardened to contain, not to make the
service safe for strangers:

- read-only root filesystem, `/tmp` is a 2 GB tmpfs, non-root user (`CAD_UID:CAD_GID`)
- `cap_drop: ALL`, `no-new-privileges`, 4 GB memory limit
- no Docker socket, no host mounts beyond the project directory
- every job runs in its own throwaway directory with a hard timeout; the whole process group is killed on expiry
- uploads are capped in size and file count; archives may not contain absolute paths, `..`, links or devices

Data flow: `/zoo` sends the text prompt to Zoo, and the KCL Zoo generated goes back to Zoo's Engine
API for export. Nothing else leaves the host; `/render`, `/convert` and `/repair` are fully local. The
Bambuddy upload happens from the CLI on the client, never from the service.

## Development

- **Live reload.** The project is mounted at `/app`; Ruby reloads via `rack-unreloader`
  (`RACK_ENV=development`) and Python is read fresh on every job, so code changes apply on the next request.
- **Rebuild** (`docker compose up -d --build`) only for `Gemfile`/`Gemfile.lock`, `pyproject.toml`/`uv.lock`
  or the `Dockerfile`.
- **Lock Python deps** without installing uv on the host:
  `docker run --rm -v "$PWD":/w -w /w ghcr.io/astral-sh/uv:0.9.23-python3.12-trixie-slim uv lock`
- **`bin/verify`** is the smoke contract (~45 s, mostly Zoo): `/health` 200; STL and STEP renders of
  `examples/bracket.py` with `X-Cad-Volume-mm3` within 1 % of the analytic 10634.528 mm³; a fit check
  exits 3; STEP → STL convert; repair of an open cube → watertight 1000 mm³; `--to-bb --dry-run`
  (skipped unless `BAMBUDDY_URL`, `BAMBUDDY_API_KEY` and `CAD_VERIFY_PIPELINE` are set); `/zoo`
  (skipped when the service has no token). Run it against any instance with `CAD_RENDER_URL=…`.
- **`bin/deploy-rsync`** pushes the checkout to a remote Docker host over ssh (compose files excluded,
  `.env` re-chmoded), for setups where the build context lives on another machine.
- **Layout.** `app.rb` orchestrates (validate → stage input → `Worker.run` → respond); `lib/` holds
  config, the bounded job limiter, the archive extractor, the op registry and the subprocess runner;
  `worker/*.py` does the geometry.

| Extend | Where |
|---|---|
| New op | `worker/<op>.py` (same `--out/--meta/--format` contract; exit 0 ok, 3 empty, 1 failure with `error` in the meta JSON) + one line in `Ops::REGISTRY` (`lib/ops.rb`) |
| New output format | One function + one line in `EXPORTERS` (`worker/exporters.py`), plus its MIME in `Ops::MIME` |
| New input format | `worker/loaders.py` + the op's `inputs` list |
| Zoo changes | `lib/zoo.rb` + `worker/zoo.py` only |

## Built for a homelab, generic by config

cad-render started in the author's homelab, where it runs behind an internal reverse proxy next to an
OpenSCAD render service and a Bambu Lab print manager, driven by coding agents. Every site-specific
value is an environment variable with a generic default, and both integrations — Zoo text-to-CAD and
the Bambuddy hand-off — are optional: without a token `/zoo` says so and everything else works.

## License

[MIT](LICENSE)
