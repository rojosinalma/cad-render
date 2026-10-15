# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- Bump `pillow` to 12.3.0 and `puma` to 7.2.1 (Dependabot alerts).

## [0.1.0] - 2026-10-16

First public release.

### Added

- `POST /render`: run a build123d Python script (project tarball + `main`, single file or inline
  source) with `-D name=value` defines, export to STL, STEP, 3MF or PNG; empty geometry is reported
  as exit 3 / `X-Cad-Empty: 1` for fit checks.
- `POST /convert`: STEP/STP and STL/3MF/OBJ/PLY/OFF in, STL/STEP/3MF/OBJ/PLY/PNG out (mesh → STEP
  refused).
- `POST /repair`: vertex merge, degenerate/duplicate face removal, winding and normal fix, hole
  filling and a manifold3d pass; STEP input is tessellated first; reports watertightness.
- `POST /zoo`: text-to-CAD via Zoo's copilot websocket (KCL) + the pinned `zoo` CLI export, to
  STEP/STL/3MF/OBJ/PLY/GLB or the raw KCL.
- `GET /health` with toolchain versions, token presence and queue state; `GET /` lists the ops.
- Response metadata: `X-Cad-Version/Empty/Warnings/Seconds/Volume-mm3/Bbox/Zoo-Id/Timeout` headers,
  or JSON with the worker log and `output_base64` when `log=1`.
- Bounded job limiter (`CAD_MAX_JOBS`, `CAD_MAX_QUEUE` → 503), per-job throwaway work dir, hard
  timeout with process-group kill (504), upload size/count caps and a safe tar extractor.
- Software-rendered isometric PNG preview (matplotlib Agg, no GPU or display).
- `bin/cad-render` CLI: `render`/`convert`/`repair`/`zoo`, `-D` defines, `--root`, `--log`, exit
  codes 0/1/2/3/4/5, and `--to-bb [--folder] [--pipeline] [--copies] [--dry-run]` to upload the
  result to a Bambuddy library and run a slicer pipeline by name.
- Hardened `compose.yaml`: read-only rootfs, tmpfs `/tmp`, `cap_drop: ALL`, `no-new-privileges`,
  4 GB memory limit, configurable `CAD_PORT`, `CAD_UID`/`CAD_GID`, `TZ`; live `.:/app` mount.
- `bin/verify` smoke contract: health, STL/STEP render with analytic volume check, fit check,
  convert, repair, Bambuddy dry run and Zoo (the last two skipped when not configured).
- `bin/deploy-rsync` to push the checkout to a remote Docker host.
- `examples/bracket.py` reference part with a known analytic volume.

[Unreleased]: https://github.com/rojosinalma/cad-render/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/rojosinalma/cad-render/releases/tag/v0.1.0
