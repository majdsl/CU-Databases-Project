# Controlled process-crash recovery experiment

**Status: 65 unit tests passed in Docker on the team laptop; the October 6, 2026
pilot (10 trials) and full run (50 trials) are verified and archived.**
See [recovery findings and charts](recovery-findings.md) for row survival, log diagnostics,
timing and evidence links. The pilot is excluded from full-run statistics.
Unit tests use mocked Docker/database operations; the archived runs are real Docker measurements.

## Question

After a client has received success responses for 1,000 single-row autocommit
inserts, which rows are readable and unchanged after a clean restart versus a
forced database-process stop? What does the server report during restart?

This first recovery experiment deliberately stops **between statements**, after
all intended writes are acknowledged. It does not exercise interrupted statements,
open uncommitted transactions, or a write of uncertain commit outcome. A failed
writer aborts preparation; the harness does not retry it or call that a valid crash trial.

The existing flight-event generator and five matched SQL schemas are reused.
The recovery sample defaults to 1,000 rows (not the storage experiment's 10,000),
with seed 20260923. Every engine receives identical values and indexes. There is
one client, and server durability/recovery settings are recorded, not assumed equal.

## Isolation and sequence

`python scripts/run_recovery.py` runs on the Windows/Linux host and uses
`compose.recovery.yaml` alone. Docker Desktop must be running Linux containers.

For each engine and stop condition:

1. Generate a fresh `cu-recovery-<UUID>-<trial>` project. Refuse existing labelled
   resources and exact-name volume/network/writer collisions. Use a new named
   `recovery_data` volume; never reuse the normal project volume.
2. Start the isolated server and wait for initial health. Check the container's
   project/service labels, its exact dedicated volume mount, and that PID 1 is
   `mariadbd` or `mysqld`. These ownership checks precede any planned stop.
3. Start a detached writer using the restricted `benchmark` SQL account. Refuse
   pre-existing tables, get the shared advisory experiment lock, create the schema,
   verify the engine, and capture actual DDL, version, settings and source metadata.
4. Execute one INSERT at a time, with autocommit enabled. Record an ID only after
   the client receives success and the affected-row count is one. After the final
   response, flush the full acknowledgment receipt to a host-mounted file and
   publish it atomically. No row read, ANALYZE, CHECK, FLUSH or connection close
   follows the final insert before the intervention. The writer waits with its
   connection and advisory lock open.
5. The host verifies the ordered IDs, count and expected dataset hash, checkpoints
   the receipt, then applies the planned intervention to the verified container:
   - `clean`: graceful stop with a 120-second timeout; require exit code 0.
   - `sigkill`: `docker kill --signal KILL`; require exit code 137.
   An OOM or a mismatched exit state invalidates the trial. No automatic restart
   policy is configured. Remove only the disposable writer after the DB has stopped.
6. Start the **same DB container with the same volume**. Launch an observer which
   polls database connectivity/SELECT 1 for up to 120 seconds (individual connection
   or query timeouts may modestly extend this). Retry only connection/readiness
   failures, never data reads or writes.
7. Read every row in primary-key order and compare every column with the expected
   dataset. Save exact missing, changed, unexpected and duplicate IDs, counts and
   a digest of the observed rows. If a read fails, record `unreadable` with its SQL
   error code; if readiness fails, record `unavailable`. Neither is zero survival.
8. After the observation, run CHECK TABLE as a diagnostic. Never issue REPAIR TABLE.
   Preserve restart logs; record engine recovery settings so automatic recovery
   can be distinguished from a manual repair. Inspect logs and diagnostic messages
   before making claims about recovery actions.
9. Checkpoint results before cleanup. Exact data recovery, or an empty MEMORY
   table with no unexpected rows, allows removal of the trial's own disposable
   resources if CHECK TABLE reports no error. Other outcomes are stopped and
   retained for review. A setup/orchestration failure aborts the run, keeps partial
   evidence and retains the failed trial's volume. It is never a success summary.

No normal-project stop, kill, volume deletion, or global Docker prune is used.
An abrupt host-script termination may leave isolated resources running; there is
no automatic resume or generic cleanup command. Review the recorded project IDs.

## Design and outcomes

The pilot has **10 trials**: five engines, each with a clean and forced restart.
The full experiment has **50 trials**: five balanced engine-order rounds and two
stop conditions per engine, each on a fresh volume. Condition order alternates
across engine positions and rounds; with five rounds it is not perfectly balanced
within each individual engine. Pilot and full-run observations remain separate.

Record the actual power settings with `--power-condition`; keep other host work
stable. We do not predict an engine ranking or interpret a completed protocol as
successful data preservation by every engine.

A readable table is classified by intact rows, missing IDs, changed values,
unexpected IDs and duplicates. The expected dataset hash is calculated independently
on the host and writer. It is an oracle, **not a pre-crash SELECT checksum**: doing
a full validation read before crashing would perturb the procedure. We rely on
client acknowledgments for the pre-crash write evidence and perform full validation
after restart. No user data is involved.

## Timing and limits

- `restart_through_verification_seconds` spans the host's restart request through
  observer completion. It includes Docker startup, observer-container launch,
  readiness polling, full data comparison and CHECK TABLE. It is **not engine-only
  recovery latency**. Compare it with its clean-restart control and read the logs.
- `observer_wait_seconds` starts inside the observer; it omits prior Docker startup.
  Neither metric precisely measures when MariaDB internally completed recovery.
- The acknowledgment receipt and host-side validation/checkpointing cause a delay
  before the crash. The writer records the last-ack UTC timestamp; the host records
  when it requests the stop and elapsed receipt-seen-to-stop-request time. Host and
  container wall-clock differences prevent treating their timestamp difference as
  an exact latency measurement. This is not an immediate crash at commit time.
- SIGKILL kills the server process while the host/kernel and filesystem cache remain
  alive. It does **not** simulate power loss, a kernel crash or storage-device failure.
- MEMORY is volatile even after clean restarts. Its lost rows do not by themselves
  establish a crash-recovery defect.
- A nontransactional engine may preserve every row in these between-statement crashes.
  That does not give it transactional atomicity or power-loss durability.
- No manual repair, forced MyRocks compaction, or forced durability tuning occurs.
  Defaults and automatic recovery settings are saved. Review SQL error codes; e.g.
  an authentication/configuration error is not evidence of an engine recovery failure.
- Restart failure has unknown row survival; retained volumes allow later diagnosis.
  Do not silently repair the table and replace the original observation.
- Results are for a small synthetic dataset and one host. Additional crash timings,
  transaction scenarios or workloads would be separate experiments.

## Run, one command at a time

After pulling the code, first rebuild and test the normal runner image:

```powershell
docker compose build runner
docker compose run --rm --no-deps runner python -m unittest discover -s tests -v
```

Then, on the **host terminal**, run the pilot (not from inside a runner container):

```powershell
python scripts/run_recovery.py --pilot --power-condition "plugged in; battery saver off"
```

The script builds separate recovery image tags. Existing `.env` credentials are
used without changing the normal database. Review the pilot before the full run:

```powershell
python scripts/run_recovery.py --full --power-condition "plugged in; battery saver off"
```

Each run saves `results/<UTC>-recovery-<id>/results.json`, a completed `summary.md`,
and per-trial acknowledgment JSON plus `restart.log`. Upload or archive the whole
run folder so the logs and receipts accompany the summary. Failed runs retain
partial evidence; preserve it rather than rerunning into the same directory.

## References

- [Docker kill](https://docs.docker.com/reference/cli/docker/container/kill/): signal semantics.
- [Docker stop](https://docs.docker.com/reference/cli/docker/container/stop/): graceful stop and forced fallback.
- [MariaDB MEMORY](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine): volatile rows.
- [InnoDB redo log](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-redo-log): recovery/durability context.
