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

## Native Linux output prerequisite

The runner uses UID/GID 10001 and writes to the host's `results/` bind mount.
On an ordinary rootful Docker host, a new directory with mode `0755` owned by a
login UID other than 10001 does not grant the runner write access. Prepare access before the first
setup build if it is not already configured. Windows Docker Desktop users can
continue to the wrapper below; these POSIX ACL commands are for native Linux.

From the repository root, check that `setfacl` is available:

```bash
command -v setfacl
```

If it is missing on Ubuntu/Debian, install the `acl` package:

```bash
sudo apt-get update
sudo apt-get install acl
```

Then grant the runner access to this directory only:

```bash
mkdir -p results
setfacl -m u:10001:rwx results
```

The ACL changes this directory's access without changing ownership, existing file
contents or permissions throughout the repository. It is not recursive. Existing
ACLs may already grant access; setup does not try to infer Docker access from Unix
mode bits. Rootless/user-remapped Docker and SELinux can require different host
configuration. Follow the relevant administrator instructions for that setup.
The actual container write probe remains the authoritative check before testing
or starting MariaDB.

Setup prints the scoped commands with your checkout's quoted absolute path before
credentials, downloads and builds. If its later write probe fails, the error repeats
those commands and the missing-utility hint. It does not execute them or change
ownership/permissions automatically. CI owns a fresh disposable directory and
grants its runner group 10001 write access while retaining host ownership; it does
not change ownership or groups on your laptop.

## Setup wrapper after prerequisites

Validated from a fresh Ubuntu CI checkout on October 15:
[85 tests and all five engines passed](https://github.com/majdsl/CU-Databases-Project/actions/runs/38824387276)
at `ead6f10`, including the output-write probe. Independent reproduction of this
wrapper on Windows remains pending.

After the prerequisites above, run `python scripts/setup_project.py` on Windows or
`python3 scripts/setup_project.py` on Linux. This wrapper is one command; the native
Linux access preparation is a separate first-run prerequisite. It resolves the repository directory
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

Setup leaves this database running. Before starting an isolated OpenFlights measurement,
stop your setup database with `docker compose stop db`, or
`docker compose -p <name> stop db` if you selected `--project-name <name>`.
Both commands retain its volume. Stop only your own lab when nobody else is using it;
do not interrupt another stack to free resources. Then follow the
[prepare → pilot → full → stop → save sequence](openflights-reproduction.md).

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

`.env` contains secrets, is ignored by Git, and must not be shared. The generator
creates a new file with POSIX mode `0600` before writing credentials, regardless of
a permissive shell umask. It preserves an existing file and its permissions; on an
existing POSIX checkout, inspect access and use `chmod 600 .env` if needed. On Windows,
restrict the containing directory/file ACL to your account; POSIX mode bits do not
establish a Windows ACL. No database port is exposed on the host; the benchmark account is
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
