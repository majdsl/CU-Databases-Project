# Verified MyRocks compression evidence

Measured on the team laptop on October 27, 2026 (Europe/Berlin; directory IDs use UTC).
The raw archive was committed as `7dd87e4fde8f015c1d5f5759f94c910e4804a807`.
The [method](../../docs/rocksdb-compression-method.md) defines the controls;
the [findings and charts](../../docs/rocksdb-compression-findings.md) interpret the full run.

| Mode | Run | Trials | Role |
| --- | --- | ---: | --- |
| Pilot | [20261027T213812Z-rocksdb-compression-501c1299](20261027T213812Z-rocksdb-compression-501c1299/summary.md) | 4 | Configuration/data/lifecycle check; excluded from statistics |
| Full | [20261027T220128Z-rocksdb-compression-ea876f45](20261027T220128Z-rocksdb-compression-ea876f45/summary.md) | 32 | Eight balanced repeats per payload/codec condition |

Each trial has 65,536 rows with 1,024-byte payloads. The four conditions cross
repetitive/high-entropy data with no compression/ZSTD. Every trial uses a fresh
owned database volume. Full measurements cover 2,097,152 verified row loads,
32,000 timed point lookups and 160 timed CRC32 scans.

## Files and review

Each directory contains `results.json`, `commands.json`, the original `summary.md`
and a separate worker/inventory JSON pair for every trial. Raw files are retained,
including source/runtime/settings, exact query streams, CF/SST metadata, file
inventories, command output and cleanup records.

The report validator regenerates the SHA-256/CRC32 data oracles, checks effective
and actual codecs, all query streams/counts, stable SST layout, clean stops, raw
file agreement, command-log checksums and all owned-resource cleanup sequences.
The full run has 1,964 successful command records and 96 container/32 volume removals.
Floating-point recalculation agrees within `1e-12` relative/absolute tolerance;
the original summaries match at their displayed precision.

All 76 published JSON files matched the reviewed ZIP bytes. The two Markdown
summaries matched after newline normalization. The local `.gitattributes` keeps
JSON bytes unchanged so original command-log SHA-256 values remain valid across
Windows/Linux checkouts. The [derived statistics](../../docs/data/rocksdb-compression-statistics.json)
label raw-byte, canonical-JSON and normalized-summary hashes separately.

Measured revision: `cd3865136c8f466d3d19a5e327c578e033478778`; both runs record no tracked
edits. All eight host and 25 worker source hashes match the reviewed sources after
accounting for CRLF source files. Pilot/full use separately built image pairs;
each pair is held fixed by immutable ID within its run. The full identities and
their limits are in [image provenance](../../docs/image-provenance.md).

## Boundaries

This is a single-client, insert-only, flush-only MyRocks experiment with automatic
compaction disabled and warm reads. Table-mapped SST lengths exclude WALs and
other datadir files; Linux allocated blocks are not physical SSD allocation.
The administrative final-flush timer is not all compression work or server-only CPU.
One laptop's repeated trials do not provide independent-machine replication.
The separate [CI smoke](../reviews/20261027-rocksdb-compression-ci/README.md) is
correctness evidence, not another full measurement.
