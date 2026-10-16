# cad-render — software design document

## Purpose

cad-render turns CAD work into HTTP calls that a script or an agent can make without a desktop
application: render a build123d script to STL / STEP / 3MF / PNG, convert between mesh and B-rep
formats, repair a broken mesh, and turn a text prompt into CAD through Zoo. One request is one
file, the service keeps no state between requests, and every result carries the metadata a caller
needs to decide what to do next (volume, bounding box, warnings, duration, "empty" flag).

## Architecture

Two layers in one container, talking over subprocesses:

| Component | Files | Role |
|---|---|---|
| HTTP front (Ruby, Roda on Puma) | `app.rb`, `config.ru`, `bin/entrypoint` | Validates requests, stages the input into a throwaway work dir, runs one worker, maps the outcome to a file or JSON response |
| Config | `lib/config.rb` | Every tunable as an environment variable with a default |
| Job limiter | `lib/job_limiter.rb` | Caps concurrent workers (`CAD_MAX_JOBS`) and the waiting queue (`CAD_MAX_QUEUE`); beyond that `503` |
| Archive extractor | `lib/project_archive.rb` | Unpacks a project tar/tgz safely (no absolute paths, `..`, links or devices; size and file-count caps) |
| Op registry | `lib/ops.rb` | One entry per op: worker script, accepted inputs, output formats, default, MIME types |
| Subprocess runner | `lib/worker.rb` | Starts `python3 worker/<op>.py --out --meta --format …` in its own process group with a hard timeout, reads the meta JSON and the log, probes toolchain versions once at boot |
| Zoo front | `lib/zoo.rb` | Prompt validation and the extended timeout for `/zoo` |
| Workers (Python) | `worker/common.py`, `render.py`, `convert.py`, `repair.py`, `zoo.py`, `loaders.py`, `exporters.py`, `health.py` | The geometry: build123d/OCP for B-rep, trimesh + manifold3d for meshes, matplotlib for PNG, websockets + the `zoo` CLI for text-to-CAD |
| CLI | `bin/cad-render` | Client in bash: tars the project, calls the API, maps outcomes to exit codes, optionally uploads to Bambuddy and runs a slicer pipeline |
| Smoke test | `bin/verify` | End-to-end contract against a running instance |

The Ruby side never imports geometry libraries and the Python side never speaks HTTP; the
boundary is the worker contract in `worker/common.py`: arguments `--out`, `--meta`, `--format` plus
op-specific ones, stdout/stderr is the log, exit `0` ok, `3` empty geometry, anything else failure
with `error` in the meta JSON.

## Data model and storage

There is no database and no persistent state. Each job gets a `Dir.mktmpdir` under `/tmp` (a tmpfs
in the container) holding the staged input, the worker's `.out.<fmt>` and `.meta.json`; the
directory is removed when the response is sent. The meta JSON carries `volume_mm3`, `bbox`,
`warnings`, `error` and, for Zoo, `zoo_id`, `zoo_conversation_id`, `kcl`.

Configuration is environment only (`lib/config.rb`), read on every access so a restart picks up
`.env` changes; secrets (`ZOO_API_TOKEN`) arrive through `.env` loaded by dotenv.

## Key flows

**Render.** `POST /render` → `stage_script` writes the project archive, the single file or the inline
source into the work dir and resolves `main` → `Ops.output_format` validates the format → `defines`
validates `D[]`/`defines` → `Worker.run("render")` → `render.py` injects the defines as module
globals, executes the script with `runpy`, picks `result` or `build()`, computes metrics and calls
the exporter → `respond` sets the `X-Cad-*` headers and streams the file, or returns the JSON
envelope when `log=1`.

**Convert / repair.** `stage_file` checks the extension against the op's `inputs`, caps the size and
writes `input.<ext>`; `convert.py` loads it (`loaders.py`, STEP via OCP, meshes via trimesh) and
exports; `repair.py` additionally merges vertices, removes degenerate faces, fixes winding and
normals, fills holes and runs a manifold3d pass, reporting watertightness in `warnings`. Mesh → STEP
is refused in `Ops.output_format` because STEP needs B-rep geometry.

**Zoo.** `lib/zoo.rb` checks the token and the prompt, then `zoo.py` opens the copilot websocket,
collects the generated KCL and exports it with the pinned `zoo` CLI (`zoo kcl export`) through Zoo's
Engine API; `kcl` as a format returns the source itself. The timeout is `ZOO_TIMEOUT_S` inside the
worker and `+30 s` as the outer kill.

**Timeout and failure.** `Worker.exec` joins the subprocess for `timeout_s`; on expiry it sends
`TERM` then `KILL` to the whole process group and the request gets `504` with `X-Cad-Timeout: 1`.
Script errors, bad input and an unconfigured Zoo are `422` with the worker log in the JSON body.

**Health.** `GET /health` returns the cached toolchain probe (`worker/health.py`: Python, build123d,
OCP, trimesh, manifold3d, `zoo` CLI versions), whether a Zoo token is present and the limiter's
counters; `503` when the probe failed, which also makes the compose healthcheck fail.

**CLI hand-off.** `bin/cad-render --to-bb` resolves the Bambuddy folder and pipeline by name before
any upload (so a typo fails fast), uploads the rendered file to the library and, with `--pipeline`,
starts the slicer pipeline. A pipeline run may enqueue a print, so an agent driving it must have a
human's approval for that exact job.

## Configuration surface

Documented in full in `docs/configuration.md` and `.env.example`. Service: `CAD_TIMEOUT_S`,
`CAD_MAX_JOBS`, `CAD_MAX_QUEUE`, `CAD_MAX_UPLOAD_MB`, `CAD_MAX_FILES`, `CAD_PYTHON`,
`ZOO_API_TOKEN`, `ZOO_API_URL`, `ZOO_POLL_S`, `ZOO_TIMEOUT_S`, plus `PORT`/`PUMA_THREADS` for Puma.
Compose: `CAD_PORT`, `CAD_IMAGE_TAG`, `CAD_UID`/`CAD_GID`, `TZ`. CLI: `CAD_RENDER_URL`,
`CAD_RENDER_TIMEOUT`, `BAMBUDDY_URL`, `BAMBUDDY_API_KEY`.

## Decisions and rationale

- **B-rep (build123d/OCP) rather than a CSG mesh kernel.** Fillets, chamfers and threads are exact
  and STEP is a first-class input and output; meshes are derived by tessellation when needed.
- **Workers as subprocesses, not in-process.** OCP is heavy and can crash or hang on bad geometry;
  a process group per job gives a hard timeout, a clean kill and isolation between requests.
- **Stateless, file in / file out.** No job store, no polling API; a caller gets the result or an
  error in the same request, which keeps the client a few lines of curl or bash.
- **Metadata in headers and exit codes.** `X-Cad-Volume-mm3`, `X-Cad-Bbox` and `X-Cad-Empty` let a
  caller check a part without parsing it; exit `3` for empty geometry turns `a - b` into a fit check.
- **Environment-only configuration with defaults in one place.** The service has nothing to persist,
  so a settings database would add state for no benefit.
- **Zoo through the copilot websocket plus the `zoo` CLI.** Zoo retired its REST text-to-CAD
  endpoint; the websocket returns KCL and the CLI exports it. Both live in `lib/zoo.rb` and
  `worker/zoo.py` so a Zoo API change touches two files.
- **Hardened container by default.** Read-only rootfs, tmpfs `/tmp`, dropped capabilities,
  `no-new-privileges`, non-root user, memory limit — because the service executes arbitrary Python
  on purpose; see `docs/security.md`.
- **Bambuddy upload in the CLI, not the service.** The service stays a pure geometry endpoint with
  no outbound credentials beyond Zoo's.
- **Multi-arch image with a per-architecture `zoo` binary.** Both are static musl builds pinned by
  SHA-256 in the `Dockerfile`; the Python wheels in `uv.lock` cover `amd64` and `arm64`.

## Current scope and non-goals

The service does rendering, conversion, repair and text-to-CAD for single parts; it has no user
accounts, no authentication of its own and no job history, and it does not render photoreal or
interactive previews (PNG is a software isometric view). Assemblies are handled as whatever the
script leaves in `result` (a `Compound` works). Authentication is left to a reverse proxy in front.

## Operations

- **Run.** `docker compose up -d` pulls `ghcr.io/rojosinalma/cad-render:${CAD_IMAGE_TAG:-latest}`;
  `.env` is bind-mounted read-only and the container runs as `CAD_UID:CAD_GID`.
- **Logs.** Everything goes to stdout (`docker compose logs -f cad-render`): Puma, `[worker] <op>
  <format> exit= ok= empty= <bytes> <seconds>` per job, `[zoo]` lines, `[http]` for unhandled
  errors with a backtrace.
- **Health.** `GET /health` (also the compose healthcheck): `ok`, versions, `zoo_token`,
  `queue{running,waiting,max_jobs,max_queue}`.
- **Upgrade.** Change `CAD_IMAGE_TAG` (or stay on `latest`) and `docker compose pull && docker
  compose up -d`. There is no data to migrate.
- **Verify.** `bin/verify` against the instance after any upgrade or configuration change.
- **Release.** Tag `vX.Y.Z`; `.github/workflows/publish-image.yml` builds and publishes the image.
