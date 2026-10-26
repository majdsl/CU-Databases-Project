# Setup and troubleshooting

The repository targets MariaDB 11.8.9, Docker Linux containers and linux/amd64.
Windows PowerShell and Ubuntu amd64 are the primary paths for the five-engine build.
The custom MyRocks image is not validated on ARM: use an amd64 Linux machine or VM
for that build. The separate [stock-image tutorial](stock-tutorial-validation.md)
passes four-engine checks on native Linux amd64 and ARM64 CI runners. Interactive
Windows/macOS reproduction remains separate. We do not
claim that emulation reproduces the benchmark timings. A remote Docker daemon is outside
this tutorial because the results bind mount must refer to this local checkout.

Install Git, Python 3.9+ and Docker with the Compose plugin. Start Docker before setup.
On Windows use Docker Desktop's Linux-container mode. On Linux your account must have
permission to run Docker; follow your Docker installation's administrator instructions.
Initial setup requires network access to images, package repositories and the pinned
OpenFlights source. The DB and runner are limited to 2 GiB and 512 MiB; allow additional
memory for Docker and builds. Recorded hardware and software are in
[the environment record](benchmark-environment.md).

## One-command setup

Validated from a fresh Ubuntu CI checkout on October 15:
[85 tests and all five engines passed](https://github.com/majdsl/CU-Databases-Project/actions/runs/38824387276)
at `ead6f10`, including the output-write probe. Independent reproduction of this
wrapper on Windows remains pending.

From the checkout, run `python scripts/setup_project.py` on Windows or
`python3 scripts/setup_project.py` on Linux. The wrapper resolves the repository directory
from its own path, checks the engine and Compose, preserves or creates credentials,
verifies the dataset, builds the runner, checks output permissions, runs unit tests,
builds/starts MariaDB, waits for health, and checks all five engines. It stops at the first
failed command, returns a nonzero exit code, and never runs performance/crash experiments.

Success ends with `SETUP PASS`. Unit-test fixture output can mention partial/failed trials
while testing error handling; the unittest conclusion must be `OK`. The actual database
check must print five engine PASS lines and an overall PASS. A failed check is not a
successful setup.

The wrapper's optional `--project-name` is used for isolated CI stacks. If you use it,
include the same `-p <name>` on every subsequent Compose command. Default instructions
use the fixed `cu-engine-lab` project; a second clone alone is not an isolated database.
Do not run this lab against an existing application database. Setup may recreate this
lab's container after a build while preserving its named volume. Avoid setup during
an active measurement or another person's use of that stack.

## Native Linux output permissions

The runner uses UID/GID 10001 and writes to the host's `results/` bind mount.
If setup reports that `/results` is not writable, grant this UID access to that directory
from the repository root (requires the host's `setfacl` utility):

```bash
mkdir -p results
setfacl -m u:10001:rwx results
python3 scripts/setup_project.py
```

This grants access to the directory without changing ownership of existing files or
making the entire repository writable. The runner creates a new folder for every run.
Read permissions normally allow you to inspect its results; if editing a generated file
is necessary, manage that file's permissions separately. Rootless/user-remapped Docker
and SELinux can require additional administrator configuration; the write probe must
pass before benchmarking. CI owns a fresh disposable directory and explicitly assigns
it to UID 10001; it does not change ownership on a user's laptop.

## Manual equivalent

If diagnosing a failed step, these are the core operations. Run separately and stop on
error; use `python3` instead of `python` on Linux. The wrapper additionally performs the
platform and results-write checks.

```powershell
python scripts/init_env.py
python scripts/fetch_openflights.py
docker compose build runner
docker compose run --rm --no-deps runner python -m unittest discover -s tests -v
docker compose build db
docker compose up -d --wait --wait-timeout 180 db
docker compose run --rm runner
```

## Common failures and safe stopping

| Symptom | Next action |
| --- | --- |
| Cannot connect to Docker API | Start Docker; verify `docker info` succeeds |
| Windows engine or unsupported five-engine architecture | Use a Linux amd64 Docker engine for the custom lab, or the separate four-engine stock tutorial on Linux ARM64 |
| Dataset hash mismatch | Preserve the unexpected file and investigate the pinned download; do not disable verification |
| Build/package download failure | Inspect the build output; restore network/package availability before retrying |
| Database unhealthy | Inspect `docker compose logs --tail=80 db` and `docker compose ps` |
| Access denied after changing credentials | Restore the credentials for the existing volume; initialization variables do not reset existing passwords |
| `setup_probe` already exists | Inspect it; only remove `engine_lab.setup_probe` if confirmed to be this lab's interrupted setup probe |
| Benchmark fails or reports partial results | Inspect its results/table before retrying; do not treat partial output as a complete comparison |

`.env` contains secrets, is ignored by Git, and must not be shared. Its generator keeps
an existing file. No database port is exposed on the host; the benchmark account is
restricted to `engine_lab`. Queries use parameters and engine substitution is disabled.

Use `docker compose stop` to stop the lab while preserving data. Normal setup never
deletes a database volume or runs a system-wide prune. CI cleanup applies only to its
unique disposable project. Stop any older standalone lab container before measurements
if it is running and competing for resources.

## Images and upgrades

The MariaDB base digest and exact MyRocks package are fixed in
[the DB Dockerfile](../docker/mariadb/Dockerfile). Its config loads ROCKSDB and sets a
128 MiB block cache. The build checks the matching server-core version. Transitive OS
packages are not fully locked. The [recorded package inventory](../evidence/environment/20261010-db-packages.txt)
and [local image ID](../evidence/environment/20261010-db-image-id.txt) describe one observed
build, not a registry image that can necessarily be pulled by that ID.

The [Python base provenance](runner-image.md) documents its digest pin; PyMySQL is pinned
with a wheel hash in `requirements.txt`. Historical benchmark metadata remains unchanged.
After saving your edits, update an existing main checkout with `git pull --ff-only`, then
rerun the setup wrapper when code or images changed. Review changes before new measurements.

References: [Compose startup and health waiting](https://docs.docker.com/reference/cli/docker/compose/up/),
[Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
