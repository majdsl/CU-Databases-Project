# Signed-snapshot paired builds — November 1, 2026

The isolated experiment now passes two uncached MariaDB builds, actual five-engine
readback against both, and clean shutdown. **Package inventories and selected runtime
configuration match; image/config IDs and filesystem diff IDs differ.** No identical
image bytes, registry retention, performance result or historical reconstruction is claimed.
The normal project Dockerfiles were not changed.

| Attempt | Exact tested source | Actual result |
| --- | --- | --- |
| [41322017709](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322017709) | `516defd8ca504f17de67b13c6f9c4d9afc27f8dc` | First signed DB build/start passed; unsupported Compose worker option prevented readback. Clean stop. Failed attempt retained. |
| [41322523394](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322523394) | `3d2cfa5efc59223bff7e981f6e2c37cd20fd4529` | Both builds/readbacks/stops passed. Artifact omitted the checksummed hidden `.gitattributes`; complete byte coverage cannot pass. |
| [41322953291](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322953291) | `ab8cc6df8ac823011e9c797e86817d9d2f6ee568` | Both builds/readbacks/stops passed; all 30 producer-checksummed files retained and independently checked after download. |

These are GitHub PR merge revisions; the final complete run's source head is
`41a39140b9d80e5ec64e3dd7710fe3501f0e558d`. Its Docker daemon reported `overlay2`,
4 CPUs, approximately 15.6 GiB RAM and 85.5 GiB physical free space before building.
Both database builds used `--no-cache --pull`, shared digest-pinned base layers on
one disposable daemon, and reused one frozen runner. No timed workload was run.

## Inspect the actual observations

[artifacts.json](artifacts.json) identifies every original artifact, size, SHA-256,
run and tested source. [attempt-3/comparison.json](attempt-3/comparison.json) and
the per-build inventories, image records, readback transcripts and shutdown records
contain the complete-run observations. [input-comparison.json](input-comparison.json)
also compares all 46 retained package-input file contents across its two builds:
they match. This comparison covers the selected package input tree only. Creation
times, retained file timestamps and APT logs can vary; the full filesystem was not
compared, so the different layer/config identities are not attributed solely to metadata.

Every enabled Ubuntu pocket is fixed to `20261031T000000Z`; the MariaDB 11.8.9
archive and exact MyRocks version are retained. All five exact InRelease hashes
passed **after APT signature verification**. Each build retains actual signed release
files, package indexes, public base keyrings and downloaded `.deb` files/hashes.
The [Dockerfile and source configuration](../../../docker/reconstruction/)
make this a tested isolated candidate strategy. Adopting it in the working build
still requires a maintained snapshot update/retention policy. No signature or TLS
check was disabled; no missing metadata was inferred from package names.

## Durable raw archives and offline verification

The original large ZIPs are published using the manual trusted-main workflow at
[the evidence release](https://github.com/majdsl/CU-Databases-Project/releases/tag/evidence-reconstruction-20261101).
Their exact expected hashes are in `artifacts.json`; the release publication must
be checked before treating that planned location as backed up. It preserves failed,
incomplete and complete archives separately without rewriting their bytes.
The smaller records are also committed here. The two large `package-inputs.tar`
files per successful artifact are omitted from this Git index; they remain in its
original release ZIP. Producer checksum lists therefore describe the complete ZIP,
not these selected local records. Attempts 1/2 additionally lack their original
hidden file because of the recorded upload defect. No missing file was manufactured.

After downloading the **complete** `snapshot-complete-41322953291.zip`, verify its
SHA-256, extract to a new directory, then run `sha256sum -c SHA256SUMS.txt` there.
The independently downloaded original ZIP's SHA-256 is
`e7f883ccc00b186e286c7dc7e8bc7640bf24beb95714e4981ed9a38ac418f995`.
The repository index has its own complete checksum coverage:

```sh
python3 evidence/reviews/20261101-snapshot-builds/verify.py
```

Privacy review found only public package inputs/keyrings and CI machine paths;
no credential values, private keys or personal home paths. No redactions were needed.
Original workspace downloads were preserved. The direct workspace release-asset
upload returned HTTP 401 and left no release; publication uses a native, scoped
GitHub Actions token instead. Actions artifacts alone expire after 30 days.

Remaining limits: Ubuntu snapshot retention is not indefinite; base images and
experimental output images have not been mirrored to project-owned registry storage;
the frozen runner was built once rather than independently twice; installed
inventories do not prove a complete lock or byte-identical outputs. These new
observations do not recover missing historical configurations or retrofit a lock
onto the original performance experiments.
