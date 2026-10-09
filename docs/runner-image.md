# Python runner image pin

## Recorded selection

On October 9, 2026, the team ran this in Windows PowerShell and supplied the complete output:

```powershell
docker buildx imagetools inspect python:3.12-slim
```

The output identified:

| Item | Recorded value |
| --- | --- |
| Image | docker.io/library/python:3.12-slim |
| Index media type | application/vnd.oci.image.index.v1+json |
| Multi-platform index digest | `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1` |
| linux/amd64 manifest digest | `sha256:2b4f19dae3a777dfc3b76730bda1e82e1f66ab2a2686fa93ca78edbfb4f04ffe` |
| linux/amd64 version annotation | 3.12.15-slim-trixie |
| linux/amd64 source revision | `2a3b794c223ab067d122719541cdd54a068732a5` |
| linux/amd64 base annotation | debian:trixie-slim |

The root Dockerfile uses:

```dockerfile
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
```

The digest selects this exact index even if the tag later moves. The index retains platform
selection; the team laptop uses linux/amd64. This pin does not validate other architectures
or the availability of MyRocks on them.

## Validation status and next steps

**Pin recorded and Dockerfile updated; post-change laptop rebuild and tests pending.**
The October 9 OpenFlights runner build displayed the matching digest prefix, and both
archived OpenFlights runs reported Python 3.12.15. This corroborates the version observed
then but is not a replacement for their original source/runtime provenance.

After pulling this change, rebuild and test, one command at a time:

```powershell
docker compose build runner
docker compose run --rm --no-deps runner python -m unittest discover -s tests -v
```

The existing suite has 82 tests. Tests do not require the database to run. No performance
rerun is needed solely to record this pin; future experiments must record their own metadata.
For a fresh checkout, fetch the pinned OpenFlights data before building as documented in
the README.

## What this pin covers

- It fixes the Python runner base image. PyMySQL remains pinned by version and wheel hash.
- Source code, downloaded data and build configuration still contribute to the final runner
  image. Record its built image identity separately when capturing a new environment.
- The MariaDB base image has its own existing pin. The custom database image installs
  MyRocks plus transitive OS packages; those packages are not all independently locked.
- Host/kernel, Docker/WSL resources, power conditions and background work are not controlled
  by this image pin. See [environment record](benchmark-environment.md).
- Archived experiment metadata remains unchanged. A new Dockerfile hash is expected for
  later runs; do not rewrite historical hashes to match it.

Treat future pin updates as deliberate changes: inspect the replacement, rebuild and test,
then record the new identity. Clean-checkout reproduction and correctness CI are still pending.
