# HTTP API

The service listens on port `9292` inside the container (`CAD_PORT` on the host). Every op is one
request, one file.

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

## Response headers

On file responses: `X-Cad-Version`, `X-Cad-Empty` (`0`/`1`), `X-Cad-Warnings` (count),
`X-Cad-Seconds`, `X-Cad-Volume-mm3`, `X-Cad-Bbox` (`xmin,ymin,zmin,xmax,ymax,zmax`), `X-Cad-Zoo-Id`
(`/zoo` only), `X-Cad-Timeout: 1` on a 504. An empty result is a `200` with `X-Cad-Empty: 1` and an
empty body.

## JSON mode

`log=1` returns JSON instead of the file: `{ok, message, empty, warnings, seconds, exit_code,
volume_mm3, bbox, format, bytes, log, output_base64}` plus `zoo_id`, `zoo_conversation_id` and `kcl`
for `/zoo`. Errors are always JSON `{ok: false, message, ..., log}`.

## Status codes

| Status | When |
|---|---|
| `200` | Done (check `X-Cad-Empty`) |
| `422` | Bad input: unknown format, invalid archive, script error, Zoo not configured, worker failure |
| `503` | Queue full (`CAD_MAX_JOBS` running and `CAD_MAX_QUEUE` waiting) or worker toolchain unavailable (`/health`) |
| `504` | Worker killed after `CAD_TIMEOUT_S` (`ZOO_TIMEOUT_S` + 30 s for `/zoo`) |

## Examples

```sh
curl -F file=@examples/bracket.py -F format=step -D - -o bracket.step http://localhost:9292/render
curl -F file=@broken.stl http://localhost:9292/repair -o fixed.stl
curl -H 'Content-Type: application/json' \
     -d '{"prompt":"a 20 mm cube with a 5 mm through hole","format":"stl"}' \
     http://localhost:9292/zoo -o cube.stl
```
