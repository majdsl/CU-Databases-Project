# MyRocks compression correctness — October 27, 2026

The four-condition compression smoke passed on a fresh Linux amd64 GitHub runner:
no compression and ZSTD, each with compressible and random-byte synthetic data.
This archive is **configuration/lifecycle correctness evidence**, not a laptop
performance experiment or a compression-ratio recommendation.

- [PR run 40577805344](https://github.com/majdsl/CU-Databases-Project/actions/runs/40577805344),
  integration job `122448796167`.
- Source head: `c430b938753e028da05a9ad071779b1b03ddb15e`.
- Tested PR merge revision: `4224b8e90bbec6fb846e5ad9b71e4eacff14a834`.
  Its tree matches the source candidate, with the unchanged main base.
- All four CI jobs passed: 132 lightweight tests/five-engine integration, seven
  offline tests under normal/optimized Python, and stock tutorial amd64/ARM64.
  The 17 new compression tests also passed locally with optimized Python.

## Evidence

[validation.json](validation.json) is the JSON record extracted from the actual
compression step's labelled output. [transcript.txt](transcript.txt) retains that
step through the validation block, with GitHub timestamps removed and LF newlines.
It is not a byte-identical copy of a local output directory. The ephemeral
`commands.json` file was not transferred; its digest remains in the validation.
The [provenance](provenance.json) records extraction, source/run identity and hashes.
[Git attributes](.gitattributes) preserve the two archived records' LF bytes.

Each of four trials verified 256 rows, effective column-family settings, real SST
codecs, point/CRC32 query answers and stable table SST layout. The host checked the
same immutable DB/runner image IDs throughout, a clean non-OOM stop, a read-only
file inventory and removal of its three owned containers and volume.
All eight host-recorded source hashes match the tested candidate, including the
fixed Dockerfiles and server configuration. The seven shared worker/host source
fingerprints agree. No tracked edits were present.

CF values agree across conditions except `COMPRESSION_TYPE` and two per-process
object-address fields (`TABLE_FACTORY::BLOCK_CACHE` and
`TABLE_FACTORY::FLUSH_BLOCK_POLICY_FACTORY`). Normalizing just the addresses makes
the latter values agree, including the factory type; the 128 MiB cache capacity
is checked numerically. Bottommost compression is the same inherited policy in
both treatments. No table-mapped SST is accepted without an explicit codec.

The payload is only 256 KiB per CI trial. These timings/file lengths cannot
substitute for the 64 MiB laptop pilot/full study, whose measurements and findings
remain pending. Automatic compaction is disabled in this protocol; the smoke
does not demonstrate steady-state compaction or physical SSD performance.

See the [method and laptop commands](../../../docs/rocksdb-compression-method.md).
