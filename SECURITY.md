# Security

## Reporting a vulnerability

Report vulnerabilities privately through the repository's Security tab:
[open a security advisory](https://github.com/rojosinalma/cad-render/security/advisories/new).
Never file them as public issues. I acknowledge reports within a few days and publish a fix and an
advisory once one is available.

## Supported versions

The latest release (and the `latest` image tag built from `main`) receives security fixes. Older
tags are not patched; upgrade to the current release.

## Threat model

cad-render executes the Python scripts it is given and has no authentication of its own. The
container hardening, data flow and secret handling are described in [docs/security.md](docs/security.md);
run the service on a trusted network or behind an authenticating reverse proxy.
