# Reproduce OpenFlights with recorded image identities

Use this host-side launcher for new pilot/full measurements after completing
[setup and the platform prerequisites](setup.md). It keeps the benchmark's dataset,
SQL, timing boundaries and default workload unchanged while recording which images
and controls actually executed it. Use `python3` instead of `python` on Linux.

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

The pilot must finish with five verified trials and a summary marked **PILOT**. Read
its raw result and summary before continuing. The session records each stage's run ID;
the original `results.json` and `summary.md` are left unchanged. One pilot round does
not estimate variability.

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
