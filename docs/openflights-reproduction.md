# Five-engine setup and repeated OpenFlights measurement

This is the complete Linux amd64 path from checkout to a verified evidence ZIP.
For a simpler first result, use the [four-engine stock tutorial](../README.md#start-here).
The full lab adds MyRocks and repeated performance measurements; the stock tutorial
checks correctness and does not establish a timing ranking.

## Set up the five-engine lab

Install Git, Python 3.9+ and Docker with Compose; start Docker and verify that
`docker info` succeeds. Windows Docker Desktop must use Linux containers.
The custom MyRocks image is validated for **Linux amd64**, not ARM emulation.
DB/runner limits are 2 GiB/512 MiB; allow additional memory for Docker and builds.
Check [actual Docker disk capacity](setup.md#disk-capacity) before building.

For a new checkout, run each command separately:

```powershell
git clone --branch main https://github.com/majdsl/CU-Databases-Project.git
cd CU-Databases-Project
```

For an existing checkout, save your edits and update before starting a session.
Run every following command from the repository root; use `python3` instead of
`python` on Linux.

**Native Linux only:** grant runner UID 10001 access to its output directory first:

```bash
mkdir -p results
setfacl -m u:10001:rwx results
```

If `setfacl` is missing, install `acl` using the
[scoped output-access instructions](setup.md#native-linux-output-prerequisite).
Windows Docker Desktop does not use these POSIX ACL commands. Rootless Docker,
user remapping and SELinux can need administrator-specific configuration; the
container write probe remains authoritative.

```powershell
python scripts/setup_project.py
```

Success requires the unit suite's `OK`, five engine PASS lines and **`SETUP PASS`**.
The wrapper preserves or creates private `.env` credentials, fetches the verified
routes dataset, builds images and checks output writes. Keep `.env` private and
unchanged for an existing volume. Setup preserves volumes and can recreate this
lab's container, so run it outside active measurements. A second clone shares the
normal Compose project name; it is not automatically isolated.
Use [setup diagnostics](setup.md#common-failures-and-safe-stopping) if any step fails.

## Measurement controls

The host-side launcher keeps the benchmark's dataset, SQL, timer boundaries and
default workload unchanged while recording the images and controls that executed it.

The [complete November 1 validation](../evidence/reproductions/20261101-ci-openflights-session/README.md)
retains real five-trial pilot/25-trial full results, clean shutdown, build records,
the exported ZIP and successful standalone verification after extraction. It
validates this workflow on a shared Linux CI host; its timings are not laptop
performance findings or independent human installation evidence.

The launcher requires the existing private `.env` and verified OpenFlights dataset.
It preserves them and creates a unique `cu-openflights-<id>` Compose project with
its own database volume. The normal lab database is not restarted or reused.
Only local Unix-socket or Windows named-pipe Docker endpoints are supported, because
the results bind mount must refer to this checkout. Remote/TCP daemons are refused.
Do not run another measurement at the same time; shared host work can affect timings.
Check [physical disk headroom](setup.md#disk-capacity) before preparing another
isolated session, especially with nested Docker's `vfs` storage driver.

Run all commands below from the repository root. Setup leaves its lab database running;
before measuring, stop that database if it is your lab and nobody else is using it:

```powershell
docker compose stop db
```

If setup used `--project-name <name>`, use `docker compose -p <name> stop db` instead.
This retains the setup volume. Do not stop another person's stack; arrange a quiet
measurement period before continuing.

## Prepare once

```powershell
python scripts/run_openflights.py --prepare
```

Preparation builds both images with unique temporary tags, resolves their immutable
IDs and writes a session manifest under `results/<timestamp>-openflights-session-<id>/`.
It prints the exact `session.json` path. Keep that path for each following command.
Leave the session in this checkout's `results/` directory until all stages are finished.
The build may reuse cached layers. An optional `--build-override <file>` supplies
an environment-specific build adapter; it is used only during preparation.
Runtime uses the standard experiment settings and the selected immutable image IDs.

The manifest records source revision/working-tree state, source and launcher hashes,
selected images, the local endpoint kind, Compose version and commands without credentials. Uncommitted source
is identified rather than represented as an unchanged commit. Do not rebuild, pull,
commit, switch revisions or edit tracked files, the manifest, runtime override or
experimental settings between stages.

## Pilot, inspect, then full

Use the printed session path, replacing the placeholder below. Describe your actual
power/host condition; the example label is appropriate only when it is true.

```powershell
python scripts/run_openflights.py --pilot --session "results/<session>/session.json" --power-condition "plugged in; battery saver off"
```

The launcher starts the new database by the selected ID and waits for health before
starting the runner. It checks ownership, actual image and CPU/memory controls before
executing the benchmark, then checks the same container again afterward. Read-only
probes surround the worker to record source/runtime, server and SQL settings. Those
probes add work outside the harness's existing timed queries and loads.
Worker output is captured and printed after that worker exits, so the command can be
quiet while it runs. Do not relaunch it because output has paused.
From a second terminal, `docker ps` shows running containers without changing the
session. The session's `stages.pilot.runner_before.container_id` (or the corresponding
`full` field) identifies the worker; `docker logs <container-id>` reads its current
output. Successful workers are removed after validation, so use the retained
`pilot-transcript.txt` or `full-transcript.txt` afterward.

The pilot must finish with five verified trials and a summary marked **PILOT**. Read
its raw result and summary before continuing. The session records each stage's run ID;
the original `results.json` and `summary.md` are left unchanged. One pilot round does
not estimate variability.

The terminal must end with `Pilot passed. Review its raw results/summary before invoking --full.`
To inspect the session without extra tools, run:

```powershell
python -m json.tool "results/<session>/session.json"
```

Check `status` is `pilot_completed` and `stages.pilot.status` is `completed`.
Use `stages.pilot.result.run_id` as `<pilot-run-id>` in the paths
`results/<pilot-run-id>/summary.md` and `results/<pilot-run-id>/results.json`.
Open those files in an editor: the summary must
be marked **PILOT**, and the raw result must have `status: "completed"` and five
trials, one per engine. Investigate any failed/partial trial before proceeding.
Use the original session path for `--full`, not either raw-run directory.

```powershell
python scripts/run_openflights.py --full --session "results/<session>/session.json" --power-condition "plugged in; battery saver off"
```

Running `--full` is the explicit step after reviewing the pilot. It requires the same
completed pilot, unchanged source, selected images, controls and power label. It does
not rebuild, pull or silently recreate existing workers. Retargeting a build tag cannot
change the IDs selected in the runtime override.

Full mode uses the existing 25-trial balanced workload: 67,663 verified routes per
trial, with five rounds per engine. Retain raw timings, per-trial means, sample SD and
the session's image/control records together. Keep pilot and full statistics separate.
Success ends with `Full run passed. Use --stop with this session to retain its database volume.`
The session now has `status: "completed"`; `stages.full.result.run_id` locates the
separate 25-trial result and summary.
Comparing hosts requires separate conditions and uncertainty; identical source/settings
do not imply identical machines or causal operating-system effects.

## Stop while retaining evidence and data

```powershell
python scripts/run_openflights.py --stop --session "results/<session>/session.json"
```

Stop verifies the owned database and selected image before requesting a clean shutdown.
It retains the session, raw results and named database volume. The launcher does not
delete volumes or run system-wide cleanup.

Failed or interrupted stages retain logs, checkpoint, container and any failed trial
table. They do not receive a success summary or an automatic retry. Inspect that state
before starting a new session. Do not delete an existing volume to clear an error.
Only successful owned worker containers are removed after validation.

## Save a completed run

`results/` is ignored by Git. A successful run and a code push do not upload the new
measurements. After a completed pilot/full session has stopped, create a portable backup:

```powershell
python scripts/archive_openflights.py --session "results/<session>/session.json" --output "openflights-evidence.zip"
```

The exporter verifies the recorded raw-file hashes and refuses to overwrite an existing
output. It includes the known session records, build records and both raw run directories,
plus checksums and an offline verifier. It excludes `.env` and retains the original files.
Store a separate copy of the ZIP and transfer the actual file when handing off results.
It is not committed to GitHub or uploaded automatically. Review any additional notes or
logs for credentials before sharing them.

Extract the ZIP, open a terminal in the extracted bundle directory, and verify it
without Docker (use `python3` on Linux):

```powershell
python verify.py
```

The verifier checks byte hashes and complete file coverage. The bundle preserves the
original `results/<session>/` and `results/<run-id>/` layout; its root also contains
`README.md`, `SHA256SUMS.txt` and `verify.py`.

For a complete command-line round trip, choose a new directory outside the checkout,
then extract and verify (use `python3` on Linux):

```powershell
python -m zipfile -e "openflights-evidence.zip" "../openflights-evidence-check"
python "../openflights-evidence-check/verify.py"
```

Expect `BUNDLE CHECKSUMS PASS`; this establishes complete byte integrity of the
export, not authenticity or a second SQL execution. The destination must be new
and empty so unrelated files do not change its coverage check. Record the ZIP's
SHA-256 and a verified durable location when handing it off; a code push does not
back up this uncommitted local file.

The local output layout is:

```text
results/
  <timestamp>-openflights-session-<id>/
    session.json
    runtime-images.compose.json
    pilot-transcript.txt
    full-transcript.txt
    ...
  <pilot-run-id>/
    results.json
    summary.md
  <full-run-id>/
    results.json
    summary.md
```

Find the raw run IDs in `session.json` at `stages.pilot.result.run_id` and
`stages.full.result.run_id`. Each maps to `results/<run-id>/` in this checkout.
Keep the session and both run directories together; the session directory alone does
not contain the individual timings. Pilot and full statistics remain separate.

## Correctness-only check

```powershell
python scripts/run_openflights.py --smoke --power-condition correctness-only
```

This prepares a separate session, checks five actual engines and the source/runtime/SQL
control path, and stops its database cleanly while retaining its volume. It runs no
timed OpenFlights experiment. `--session <path>` can use an already prepared unused
session, and `--build-override <file>` can adapt a new build to the execution environment.
CI runs this path separately from performance evidence.

The [original method](openflights-method.md) explains the workload and its limits.
The [cloud reproduction](openflights-linux-reproduction.md) retains the older mutable-tag
execution record honestly; this launcher does not retroactively fill its missing
per-run runner inspection. Zane's physical-laptop results will retain their own exact
tested revision and conditions when received.
