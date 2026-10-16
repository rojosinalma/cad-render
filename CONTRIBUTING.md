# Contributing

## Running it locally

```sh
cp .env.example .env
cp compose.override.yaml.example compose.override.yaml
docker compose up -d --build
curl http://localhost:9292/health
```

The override mounts the checkout at `/app` with live reload; details in
[docs/development.md](docs/development.md).

## Tests

`bin/verify` is the smoke contract — run it against the instance you changed:

```sh
bin/verify                                   # http://localhost:9292
CAD_RENDER_URL=http://host:9292 bin/verify
```

Zoo and Bambuddy checks are skipped with a warning when they are not configured. A change to a
worker, an exporter or the response contract should keep every check green; add a check there when
you add behaviour that can break.

## Code style and layout

- Ruby: Roda routes in `app.rb` only orchestrate; logic lives in `lib/`. `snake_case` methods,
  keyword arguments for multi-parameter methods, frozen constants, no business logic in routes.
  `ruby -wc` must be clean.
- Python workers in `worker/` follow the `--out/--meta/--format` contract from `worker/common.py`;
  exit 0 ok, 3 empty geometry, 1 failure with `error` in the meta JSON. Dependencies are pinned in
  `pyproject.toml` and locked in `uv.lock`.
- Every tunable is an environment variable with a default in `lib/config.rb` and a line in
  `.env.example` and `docs/configuration.md`.
- Shell (`bin/`): `set -euo pipefail`, `shellcheck`-clean.

## Commits and PRs

- Plain, descriptive commit messages in the imperative ("Add PLY loader"), one logical change per
  commit. Every commit and tag is GPG-signed (`git config commit.gpgsign true`).
- Open a PR against `main`; say what changed and how you verified it (`bin/verify` output is enough).
- Add a line under `## [Unreleased]` in `CHANGELOG.md` for anything user-visible.

## Documentation

The README stays short (what it is, requirements, installation, usage, development, licence).
Everything else lives in `docs/` and the repository-level documents:

| File | Content |
|---|---|
| `CHANGELOG.md` | Keep a Changelog; one line per user-visible change under `Unreleased` |
| `SECURITY.md` | how to report a vulnerability, supported versions |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 |
| `docs/cli.md` | `bin/cad-render` usage, options, exit codes, environment |
| `docs/writing-parts.md` | the part contract, `-D` defines, fit checks, the reference part |
| `docs/api.md` | routes, headers, JSON mode, status codes |
| `docs/configuration.md` | every environment variable for the service, compose and CLI |
| `docs/security.md` | threat model, hardening, data flow |
| `docs/development.md` | dev override, locking, smoke test, layout, image build |
| `docs/SDD.md` | software design document |
| `docs/releases/` | release notes per version |

## Releasing

1. Bump `VERSION` and `pyproject.toml`, move the `Unreleased` entries in `CHANGELOG.md` under the new
   version and write `docs/releases/vX.Y.Z.md`.
2. Commit, sign-tag `vX.Y.Z` (`git tag -s`) and push the tag; `publish-image.yml` publishes
   `ghcr.io/rojosinalma/cad-render:X.Y.Z`, `:X.Y` and `:sha-<short>`.
3. Create the GitHub release from the tag with the release notes.

cad-render is licensed under the AGPL-3.0; contributions are accepted under the same licence.
