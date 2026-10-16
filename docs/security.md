# Security

**Scripts are arbitrary Python executed inside the container, and there is no authentication.**
Run cad-render on a trusted network for trusted clients (your own tools and agents), or put it
behind a reverse proxy that authenticates. The container is hardened to contain, not to make the
service safe for strangers:

- read-only root filesystem, `/tmp` is a 2 GB tmpfs, non-root user (`CAD_UID:CAD_GID`)
- `cap_drop: ALL`, `no-new-privileges`, 4 GB memory limit
- no Docker socket, no host mounts beyond the read-only `.env`
- every job runs in its own throwaway directory with a hard timeout; the whole process group is killed on expiry
- uploads are capped in size and file count; archives may not contain absolute paths, `..`, links or devices
- the `zoo` CLI binary is pinned by version and SHA-256 in the `Dockerfile`

## Data flow

`/zoo` sends the text prompt to Zoo, and the KCL Zoo generated goes back to Zoo's Engine API for
export. Nothing else leaves the host; `/render`, `/convert` and `/repair` are fully local. The
Bambuddy upload happens from the CLI on the client, never from the service.

## Secrets

`ZOO_API_TOKEN` lives in `.env` (keep it `0600`; `compose.yaml` mounts it read-only and runs the
container as its owner's uid). `BAMBUDDY_API_KEY` is only ever read by the CLI on the client.

## Reporting

Report a vulnerability through a private GitHub security advisory on the repository rather than a
public issue.
