# Development

## Running from the checkout

`compose.yaml` pulls the published image and runs it in production mode. For development, copy the
override example and build locally:

```sh
cp compose.override.yaml.example compose.override.yaml   # git-ignored
docker compose up -d --build                             # first build: a few minutes (OCP / build123d wheels)
```

The override builds the image from the checkout, mounts the project at `/app` and sets
`RACK_ENV=development`: Ruby reloads via `rack-unreloader` and Python is read fresh on every job, so
code changes apply on the next request. Rebuild (`docker compose up -d --build`) only for
`Gemfile`/`Gemfile.lock`, `pyproject.toml`/`uv.lock` or the `Dockerfile`.

Lock Python dependencies without installing uv on the host:

```sh
docker run --rm -v "$PWD":/w -w /w ghcr.io/astral-sh/uv:0.9.23-python3.12-trixie-slim uv lock
```

## Smoke test

`bin/verify` is the smoke contract (~45 s, mostly Zoo): `/health` 200; STL and STEP renders of
`examples/bracket.py` with `X-Cad-Volume-mm3` within 1 % of the analytic 10634.528 mm³; a fit check
exits 3; STEP → STL convert; repair of an open cube → watertight 1000 mm³; `--to-bb --dry-run`
(skipped unless `BAMBUDDY_URL`, `BAMBUDDY_API_KEY` and `CAD_VERIFY_PIPELINE` are set); `/zoo`
(skipped when the service has no token). Run it against any instance with `CAD_RENDER_URL=…`.

## Layout

- `app.rb` orchestrates (validate → stage input → `Worker.run` → respond).
- `lib/` holds config, the bounded job limiter, the archive extractor, the op registry, the
  subprocess runner and the Zoo front.
- `worker/*.py` does the geometry; each worker is a subprocess with the `--out/--meta/--format`
  contract.
- `bin/cad-render` is the client CLI, `bin/verify` the smoke test, `bin/entrypoint` starts Puma.

| Extend | Where |
|---|---|
| New op | `worker/<op>.py` (same `--out/--meta/--format` contract; exit 0 ok, 3 empty, 1 failure with `error` in the meta JSON) + one line in `Ops::REGISTRY` (`lib/ops.rb`) |
| New output format | One function + one line in `EXPORTERS` (`worker/exporters.py`), plus its MIME in `Ops::MIME` |
| New input format | `worker/loaders.py` + the op's `inputs` list |
| Zoo changes | `lib/zoo.rb` + `worker/zoo.py` only |

## Image

`.github/workflows/publish-image.yml` builds `linux/amd64` and `linux/arm64` on native runners and
publishes the manifest to `ghcr.io/rojosinalma/cad-render` (`latest` from `main`, `X.Y.Z` and `X.Y`
from `v*` tags, `sha-<short>` always). The `zoo` CLI is downloaded per architecture with a pinned
checksum; bump `ZOO_CLI_VERSION` and both `ZOO_CLI_SHA256_*` build args together.
