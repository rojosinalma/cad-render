<!-- Title in the imperative, e.g. `Add PLY loader` or `Fix repair of non-manifold STEP input`. -->

## What

<!-- One or two sentences. Link the issue: Closes #123 -->

## Why

## Checklist

- [ ] `bin/verify` passes against the instance I changed
- [ ] `ruby -wc` clean on changed Ruby, `python -m py_compile` on changed workers, `shellcheck` on changed scripts
- [ ] `docs/` and `.env.example` updated when a setting, route, header, format or CLI option changed (see CONTRIBUTING.md → Documentation)
- [ ] A line under `## [Unreleased]` in `CHANGELOG.md` for anything user-visible
- [ ] Commits are GPG-signed
