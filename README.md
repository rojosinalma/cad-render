# cad-render

Headless B-rep CAD service: renders [build123d](https://build123d.readthedocs.io) Python scripts to
STL / STEP / 3MF / PNG, converts and repairs meshes, and generates STEP from a text prompt via
[Zoo](https://zoo.dev) text-to-CAD. Pairs with the `cad-render` CLI, which can also hand the result
to Bambuddy's File Manager and start a slicer pipeline.

## Run

Docker only. `docker compose up -d --build` (port 9292). The project is mounted at `/app`, so Ruby
and Python changes apply on the next request; rebuild only for `Gemfile`, `pyproject.toml`/`uv.lock`
or the `Dockerfile`.

## API

| Route | Input | Output |
|---|---|---|
| `POST /render` | multipart `project` (tar/tgz) + `main`, or `file`, or `source`; `format=stl\|step\|3mf\|png`; `D[]=name=value`; `log=1` | file + `X-Cad-Empty/Warnings/Seconds/Volume-mm3/Bbox` |
| `POST /convert` | `file`, `format` | same |
| `POST /repair` | `file` (stl/3mf/obj/ply/step), optional `format` | same |
| `POST /zoo` | JSON `{prompt, format}` | file + `X-Cad-Zoo-Id` |
| `GET /health` | | `{ok, python, build123d, zoo_cli, queue}` |

`log=1` returns JSON with the worker log and `output_base64` instead of the raw file. Scripts expose
`result` at module level or a `build()` function; `-D name=value` become module globals before the
script runs (see `examples/bracket.py`).

## Configure

Env vars, defaults in `lib/config.rb`: `CAD_TIMEOUT_S` (300), `CAD_MAX_JOBS` (2), `CAD_MAX_QUEUE` (8),
`CAD_MAX_UPLOAD_MB` (100), `CAD_MAX_FILES` (2000), `ZOO_POLL_S` (5), `ZOO_TIMEOUT_S` (600).
Secrets in `.env` (see `.env.example`): `ZOO_API_TOKEN`.

## Verify

`bin/verify` (needs `cad-render` on PATH and `CAD_RENDER_URL`): health, STL + STEP render with an
analytic volume check, fit check, convert, repair, `--to-bb --dry-run`, Zoo.
