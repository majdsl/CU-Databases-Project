# Concurrent writes: database CPU and lock-wait observations

Status: 30 pilot and 150 full trials are archived and validated. See the
[CPU and lock-wait findings and charts](write-diagnostics-findings.md).
This extends the [earlier concurrency experiment](concurrency-method.md), whose
[CPU diagnostic](cpu-findings.md) measured the runner, not database CPU or locks.
Old evidence is retained unchanged and must not be pooled with this experiment.

## Question and controls

When the same total autocommit updates run with 1, 2 or 4 clients, do throughput,
database CPU and observed lock waits change together? Compare disjoint rows with
a shared 16-row hotspot. A hotspot can produce little measurable waiting when
transactions are short; zero observed waits does not prove absence of contention.

All five engines use the existing identical `sql/benchmark/*.sql` schemas and
seeded synthetic event rows. `benchmarks/concurrency.py` supplies the exact same
key-stream generator, barrier-synchronized workers and final-data oracle. Every
UPDATE increments one fare by one and must affect exactly one row. No ambiguous
write or deadlock is retried. Full before/after row verification is outside timing.

| Mode | Rows per trial | Total updates per trial | Rounds | Trials |
| --- | ---: | ---: | ---: | ---: |
| smoke | 100 | 100 | 1 | 30 |
| pilot | 10,000 | 1,000 | 1 | 30 |
| full | 10,000 | 10,000 | 5 | 150 |

Every condition has the same total work at all client counts. Five rounds balance
engine positions. Six pattern/client conditions rotate each round but are not
perfectly position-balanced across five rounds. The repeat is the trial, not each
update. Report mean and sample SD across five trials per condition; exclude pilot
and smoke timings from performance conclusions. Pilot has fewer operations to
check lifecycle, not to estimate full-run variability.

An isolated database gets two CPUs and 2 GiB; the runner gets two CPUs and 512 MiB.
These are quotas, not dedicated cores. Query cache is disabled, strict mode forbids
engine substitution, and actual engine/DDL are checked. Record settings, image IDs,
source hashes, power and runtime. Cache and durability budgets remain unequal;
see [budget inventory](cache-and-durability.md). The fixed InnoDB pool is 128 MiB.

## Three observation windows

1. **Throughput:** barrier release until the last successful update finishes.
   It includes scheduling, Python, driver/network and SQL work. Per-update latencies
   are retained. It is not pure server execution time.
2. **Runner CPU and SQL counters:** runner CPU uses the existing telemetry around
   worker setup, updates and teardown. Global SQL snapshots bracket that worker
   call. Snapshot durations and the inner call duration are saved; snapshots are
   not atomic across all server counters. No continuous peak-wait sampling occurs.
3. **Database-container CPU:** host `docker exec ... cat` reads cgroup-v2 `cpu.stat`
   and `cpu.max` before launching the writes runner and after it returns. This
   wider window includes startup, connections, status observations, output and
   teardown. It excludes table loading and final row verification, but background
   work caused by earlier loads can continue. Healthchecks, server background
   threads and the tiny `cat` observer also contribute. This is container CPU,
   not just `mariadbd` and not query CPU attributed to individual statements.

CPU seconds = `usage_usec` delta / 1,000,000. Average cores divides by the midpoint
wall interval **between CPU samples**, never by the narrower throughput time.
The host timestamps both ends of each sample call and retains minimum/maximum
wall bounds reflecting observer latency. No idle CPU subtraction is performed.
Container replacement/restart, quota change, missing usage or decreasing counters
abort measurement. This implementation requires readable cgroup v2 and two-CPU
quotas; unsupported telemetry fails explicitly rather than becoming zero CPU.

## Lock counter interpretation

- `Table_locks_immediate` and `Table_locks_waited`: global server table-lock event
  counts. They neither measure wait duration nor enumerate every internal lock.
- `Innodb_row_lock_waits`: global InnoDB row-lock wait count.
- `Innodb_row_lock_time`: cumulative InnoDB row-lock time, documented in milliseconds.
  It is aggregate across waits, not wall-clock runtime or a percent of elapsed time.
- `Innodb_row_lock_current_waits`: an endpoint gauge, saved before/after rather than
  subtracted as a cumulative counter. Brief intervening waits can be missed.

Missing counters remain null/unavailable. Cumulative resets fail validation.
InnoDB counters are relevant to InnoDB, not equivalent MyRocks row-lock telemetry;
raw snapshots are retained for every engine but summaries label other engines
not applicable. Table-lock counters do not cover all metadata/internal waits.
Changes are observations in an otherwise isolated database, not proof of a single
bottleneck. Do not infer causality from CPU/throughput correlation alone.

## Run from Windows PowerShell, repository root

Prerequisites: completed normal setup (including existing local `.env`), Python
3.9+, Docker Desktop Linux amd64 engine with Compose and cgroup v2. Stop unrelated
benchmark workloads, plug in and disable battery saver, then record actual conditions.
The normal stack can be stopped while retaining its data:

```powershell
docker compose stop
```

The host orchestrator builds its own images and runs a separate project:

```powershell
python scripts/run_write_diagnostics.py --pilot --power-condition "plugged in; battery saver off"
```

Review the saved `results.json`, all stage outputs and `summary.md`. Only after a
successful pilot and review, run:

```powershell
python scripts/run_write_diagnostics.py --full --power-condition "plugged in; battery saver off"
```

Linux amd64 uses the same Python commands (`python3` where required). Other
architectures remain unverified due to the MyRocks image. CI uses `--smoke` for
correctness only. Full mode runs 450 short-lived runner containers, so allow time;
keep other workloads paused. No Docker socket is mounted inside containers.

## Isolation, evidence and failure handling

`scripts/run_write_diagnostics.py` accepts only generated `cu-writes-<uuid>-1`
projects and rejects any pre-existing labeled resources. It checks container labels
and the expected named volume. One fresh server/volume is reused across trials
within a run; tables are loaded anew each trial and dropped only after exact final
verification. This is warm, reused-server work, not cold-cache or sustained saturation.
Both privilege scopes remain unchanged: the benchmark account owns only `engine_lab`;
SQL counters do not require granting administrative database privileges.

The host checkpoints each stage under a unique `results/*-write-diagnostics-*`
directory and saves three raw stage outputs per trial. It independently regenerates
initial/final hashes, checks counts and telemetry arithmetic, then validates the
complete schedule. A successful run stops cleanly and removes only its own new
isolated volume. On failure, partial output, logs and that volume are retained;
there is no successful summary. Investigate the printed project name before any
manual cleanup. Never delete the normal lab volume to troubleshoot this experiment.

This does not equalize storage guarantees, isolate OS/VM effects, measure lock
fairness, prove deadlock behavior, instrument all engines' internal latches, or
replace longer server-saturation trials. Report these limits alongside findings.

References: [MariaDB server status variables](https://mariadb.com/docs/server/server-management/variables-and-modes/server-status-variables),
[InnoDB status variables](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/system-variables/innodb-status-variables),
[Linux cgroup v2 CPU interface](https://docs.kernel.org/admin-guide/cgroup-v2.html).
