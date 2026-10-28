# MyRocks compression: a controlled flush-only experiment

**Status:** the four-condition laptop pilot and eight-round/32-trial full run are
[verified and archived](../evidence/rocksdb-compression/README.md), with
[findings and charts](rocksdb-compression-findings.md). The separate Linux amd64
[CI smoke passed](../evidence/reviews/20261027-rocksdb-compression-ci/README.md);
it is a small correctness check, not performance evidence.
This protocol investigates an engine option separately from the existing five-engine
comparison. It does not revise the historical OpenFlights or storage measurements.

## Question and treatments

For a fixed MyRocks table, what changes when its SST compression policy is
`kNoCompression` versus `kZSTD`? Measure actual table-mapped SST file lengths,
insert execution, forced flush completion and warm reads. Use two synthetic data
profiles so a result on very repetitive values has a high-entropy control.

The worker creates one table:

```sql
CREATE TABLE compression_rows (
  id INT NOT NULL,
  payload VARBINARY(1024) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=ROCKSDB;
```

An integer primary key and bounded binary payload avoid collation and secondary-index
differences. Binary bytes retain the high-entropy control without character conversion.
The table has one primary index; no other user table is present in its fresh database.
This is synthetic engine-mechanism data, not additional OpenFlights route records.

Each profile has 65,536 rows and 64 MiB of payload in pilot/full mode:

- **Compressible:** a deterministic row/route prefix and repeated reference text,
  truncated to exactly 1,024 bytes. Values still encode each row's identity.
- **Random:** 1,024 deterministic SHAKE-256 bytes per row, seeded with `20261027`.
  This is a high-entropy control, not encrypted production data.

Within a profile, both codecs receive identical values, insertion batches and query
IDs. Every row is checked against its generation rule and a SHA-256 digest; a separate
host process computes the expected digest and CRC32 sum. The two profiles remain
separate statistical groups.

## Configuration and layout controls

Both treatments use the same built MariaDB 11.8.9 image and Python runner image,
identified by immutable local image IDs. Each image is built once per invocation;
every trial in that invocation uses those IDs. Separate invocations can select
different builds because transitive OS packages are not fully locked. Preserve
both IDs and source hashes; pilot and full statistics are never pooled.

Every trial gets a new database container and named volume, with:

- DB quota 2 CPUs / 2 GiB; runner quota 1 CPU / 512 MiB.
- MyRocks block cache 128 MiB; column-family write buffer 16 MiB.
- `compression` set to the selected codec; `bottommost_compression` fixed to
  `kDisableCompressionOption` (inherit) for both treatments. The primary codec is
  the only varying column-family option supplied by the harness.
- Automatic column-family compaction disabled in both treatments; no per-level
  compression override. This isolates a bounded post-flush layout rather than a
  production compaction policy.
- Strict SQL/no engine substitution, query cache off, binary logging off and
  `rocksdb_flush_log_at_trx_commit=1`.

MyRocks options are supplied before the new server initializes. The worker checks
the actual engine, effective `ROCKSDB_CF_OPTIONS`, block-cache size and table DDL.
The SST join through `ROCKSDB_DDL`, `ROCKSDB_INDEX_FILE_MAP` and `ROCKSDB_SST_PROPS`
then checks the table's actual file-level codec. An unavailable codec or ignored
configuration aborts; there is no automatic fallback.

After insertion, an administrative connection requests a memtable flush. The SST
properties must cover every inserted entry, and their layout must stay unchanged
through the read measurements. The administrative password is generated for this
disposable server; timed data operations use its restricted benchmark account.

After a verified clean stop (exit 0 and no OOM), a root helper reads only this owned
volume through a read-only mount. It uses the pinned runner image, has no network
and records file lengths/allocation for SSTs. Only unique files mapped to the table
contribute to its reported bytes. Missing files, live/unclean databases and invalid
inventories cannot produce a successful summary.

These are SST apparent bytes inside the Docker Linux volume, including file
metadata/index/filter overhead. They exclude WALs and other datadir files and are
not physical SSD allocation or a continuation of the whole-datadir storage experiment.
The SST codec field is a file-level property; individual block encodings are not inspected.

## Timings, repetitions and verification

Insertion uses autocommit and batches of 500 rows. `load_execute_seconds` sums
driver execute/completion intervals, excluding payload generation. The separate
`load_with_generation_seconds` is whole-loop wall time. `forced_flush_seconds`
measures the administrative flush statement; SST coverage is verified afterward.
Memtable flushes can already occur during insertion; the final request does not
time all compression work. None of these measures isolates server compression CPU.

The runner then streams and verifies the entire table, warming data, and performs
50 untimed point lookups. Each pilot trial measures 200 point lookups and three
full CRC32 aggregates; full mode uses 1,000 lookups and five aggregates. Every answer
is checked. The aggregate reads payloads and computes their CRC32 sum, so its time
also includes checksum work. The primary-key EXPLAIN plan is saved and checked.

| Mode | Rows per trial | Rounds | Trials | Purpose |
| --- | ---: | ---: | ---: | --- |
| Smoke | 256 | 1 | 4 | Actual SQL/configuration/file/lifecycle correctness |
| Pilot | 65,536 | 1 | 4 | Inspect evidence and laptop resource behaviour |
| Full | 65,536 | 8 | 32 | Repeated, balanced measurements |

The four conditions are the two profiles crossed with the two codecs. The eight-round
schedule places each condition twice in every trial position; every pair appears
in either relative order four times. Fresh volumes remove reused table/server state,
but host cache, temperature and scheduling can still carry over.

The statistical unit is one trial/round for a given profile/codec: average read
samples within a trial, then report mean and sample SD across eight trial means.
Load/flush/file metrics likewise have eight full observations per condition.
Pilot/smoke SD is unavailable, not zero, and supports no performance conclusion.

## Run on the measurement laptop

Requirements: a Git checkout, local Python 3.9+, and a local Linux amd64 Docker
engine on an Intel/AMD x64 host. Windows PowerShell and Ubuntu are the intended
host paths. No plotting dependency, downloaded route data or existing `.env` is
needed by this host orchestrator. The normal Dockerfile can still contain route
data if the checkout was previously prepared.

From the repository root, stop the ordinary lab while preserving its volume:

```powershell
docker compose stop
```

Stop other benchmark/tutorial containers and heavy work. Keep the charger connected
and record actual battery-saver/power settings. Then run:

```powershell
python scripts/run_rocksdb_compression.py --pilot --power-condition "plugged in; battery saver off"
```

On Ubuntu use `python3`. The preflight refuses running normal-lab or recognised
experiment containers for pilot/full. It records Docker resources, source hashes,
the Git revision and whether tracked edits were present. The worker's shared source
fingerprints must match the host's recorded files.

Review the complete pilot `results.json`, four worker JSON files, four inventories,
`commands.json` and `summary.md` under `results/<run-id>/`. Only then run:

```powershell
python scripts/run_rocksdb_compression.py --full --power-condition "plugged in; battery saver off"
```

Archive the raw result directory after review. Do not combine pilot and full
statistics. The October 27 runs are [archived](../evidence/rocksdb-compression/README.md);
their [offline generator](../scripts/report_rocksdb_compression_findings.py) validates
the raw files and reproduces the scoped findings without Docker.

## Resource ownership, failure and scope

This orchestrator creates `cu-compression-<random-token>-<trial>` resources directly
with Docker; it does not use the normal Compose stack or read/change its `.env`.
The database has no network or published port; the worker shares only that database's
network namespace for loopback SQL. Private Docker inspection output and generated
passwords are omitted/redacted in command logs. Personal host paths and Docker
context endpoints are excluded from recorded metadata.

Existing names are refused. Before stopping/removing resources, the host checks
immutable IDs, ownership labels, pinned images, resource limits, network modes and
the expected named volume. Successful trials remove their own stopped containers
and volume. Failed trials keep a failed checkpoint, stop validated owned containers
when possible, and retain their volume for inspection. There is no system prune,
production-table deletion or normal-lab volume cleanup. Inspect partial evidence
before retrying; a failed run cannot be summarized as completed.

The full table may fit in the block cache. Warm-read outcomes therefore do not
measure cold decompression or physical-disk latency. Disabling automatic compaction
also excludes steady-state LSM behaviour and compaction cost. Results apply to this
single-engine, single-client, insert-only synthetic protocol, not general compression
ratios, server CPU cost, durability comparisons or a five-engine ranking.

References: [MyRocks compression](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-and-data-compression),
[system variables](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-system-variables),
[SST properties](https://mariadb.com/docs/server/reference/system-tables/information-schema/information-schema-tables/information-schema-myrocks-tables/information-schema-rocksdb_sst_props-table),
[Docker container networking](https://docs.docker.com/engine/network/#container-networks).
