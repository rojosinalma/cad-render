# Configuration

Everything is an environment variable with a generic default. Secrets go in `.env` (loaded by the
app with dotenv and bind-mounted read-only into the container), never in `compose.yaml`
`environment:`. `.env.example` lists every variable with its default.

## Service (`lib/config.rb`)

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

Puma reads `PORT` (default `9292`) and `PUMA_THREADS` (default `8`) in `bin/entrypoint`; `RACK_ENV`
is `production` in `compose.yaml` and `development` enables `rack-unreloader`.

## Compose (`compose.yaml`)

| Variable | Default | Meaning |
|---|---|---|
| `CAD_PORT` | `9292` | Host port |
| `CAD_IMAGE_TAG` | `latest` | Tag of `ghcr.io/rojosinalma/cad-render` to pull |
| `CAD_UID` / `CAD_GID` | `1000` / `1000` | Container user — match the owner of `.env` (0600) so it is readable |
| `TZ` | `UTC` | Container time zone (log timestamps) |

## CLI (`bin/cad-render`)

| Variable | Default | Meaning |
|---|---|---|
| `CAD_RENDER_URL` | `http://localhost:9292` | Service base URL |
| `CAD_RENDER_TIMEOUT` | `900` | curl `--max-time` per request (seconds) |
| `BAMBUDDY_URL` | — | Bambuddy base URL, required for `--to-bb` |
| `BAMBUDDY_API_KEY` | — | Bambuddy API key, required for `--to-bb` |

The CLI reads these from the shell environment, not from `.env`.
