# OpenFlights reproduction on managed cloud Linux — October 30, 2026

The setup, pilot and full OpenFlights run completed on a fresh isolated checkout of
`main` at **`5afc5f03f697c3ad1ed92feafade0d49e3261cd0`**. This is the tested code
revision; the later archive commit publishes the evidence without changing that identity.
This record adds actual database measurements on a second computing environment,
separate from the original laptop results, offline report reproduction and hosted CI.

The executor has **Debian 13 userspace, nested Docker and a Linux amd64 kernel**.
The database image is based on Ubuntu 24.04. This is not a physical Ubuntu install,
a controlled Linux-versus-Windows experiment, or Zane's independent laptop reproduction.
That teammate package remains pending and can be archived with its own tested revision,
setup/tutorial/report logs and physical-machine measurements when received.

## Evidence and verification

| Run | Archived raw results and original summary | Scope |
| --- | --- | --- |
| Original laptop pilot | [20261009T152651Z-openflights-b44366ef](../evidence/openflights/20261009T152651Z-openflights-b44366ef/) | 5 trials; excluded from comparison statistics |
| Original laptop full | [20261009T160813Z-openflights-6884f225](../evidence/openflights/20261009T160813Z-openflights-6884f225/) | 25 trials; 5 rounds per engine |
| Cloud Linux pilot | [20261030T184911Z-openflights-329f0869](../evidence/openflights/20261030T184911Z-openflights-329f0869/) | 5 trials; excluded from comparison statistics |
| Cloud Linux full | [20261030T184936Z-openflights-85032cd6](../evidence/openflights/20261030T184936Z-openflights-85032cd6/) | 25 trials; 5 rounds per engine |

The [reproduction archive](../evidence/reproductions/20261030-cloud-linux-openflights/)
contains metadata, commands, build adapters, a measured-source snapshot, package inventory,
setup/database/benchmark transcripts, checksums and a runnable validator. New raw results and summaries were copied
byte-for-byte from the local result folders. Original laptop files were not rewritten.

- Setup passed all **140 unit tests**, the output-write probe, database health and actual
  engine/three-row checks for InnoDB, Aria, MyISAM, MEMORY and ROCKSDB.
- The cloud pilot/full verified **338,315 / 1,691,575 row loads**, respectively.
  Each trial contains all 67,663 routes, 200 timed point lookups, 5 scans and 100 source
  aggregates. The harness checks exact rows and each query answer against its Python oracle.
- Recalculation validates completed status, balanced schedules, finite sample counts,
  row digests, actual DDL, ANALYZE diagnostics, access plans, seeded query streams,
  source cardinalities, stored summaries and statistics for all four runs.
- Dataset manifest/digest, workload configurations, schedules, query streams and all recorded
  global/session controls match across hosts. Relevant OpenFlights code, helper and schema
  fingerprints agree after line-ending normalization; the root runner Dockerfile evolved.
  Matching settings and source logic do not establish identical images or environments.

The 32 fingerprinted source files from the tested revision are retained under
`measured-source/` in the archive and checked against the original cloud manifests.
Historical fingerprints are compared with that snapshot, so a future Dockerfile edit
does not silently substitute today's build source for the measured one. The runnable
validator uses the repository's report-validation logic to recompute rows and statistics.

## Full-run comparison

Values are **mean ± sample SD across five trials per engine on each host**. For read
metrics the statistical unit is one trial's mean, not an individual query. Percent change
is `(cloud mean / laptop mean - 1) × 100`; positive means longer completion time.
Pilots and machines are never pooled. The SD is descriptive variability, not a confidence
interval, and no statistical significance or paired-machine inference is claimed.

| Engine | Metric | Laptop mean ± sample SD | Cloud mean ± sample SD | Cloud mean change |
| --- | --- | ---: | ---: | ---: |
| InnoDB | Load (s) | 1.1840 ± 0.0383 | 1.2853 ± 0.1643 | +8.56% |
| InnoDB | Point lookup (ms) | 0.2413 ± 0.0057 | 0.2211 ± 0.0525 | -8.37% |
| InnoDB | Full scan (ms) | 11.4745 ± 0.4860 | 16.6714 ± 3.5732 | +45.29% |
| InnoDB | Source aggregate (ms) | 0.2173 ± 0.0085 | 0.2258 ± 0.0494 | +3.92% |
| Aria | Load (s) | 2.0078 ± 0.0305 | 2.4686 ± 0.3139 | +22.95% |
| Aria | Point lookup (ms) | 0.2479 ± 0.0069 | 0.3466 ± 0.1783 | +39.81% |
| Aria | Full scan (ms) | 9.7694 ± 0.4150 | 13.4014 ± 1.4453 | +37.18% |
| Aria | Source aggregate (ms) | 0.2441 ± 0.0112 | 0.2616 ± 0.0441 | +7.17% |
| MyISAM | Load (s) | 0.7932 ± 0.0213 | 1.0404 ± 0.0770 | +31.17% |
| MyISAM | Point lookup (ms) | 0.2374 ± 0.0091 | 0.2943 ± 0.0271 | +23.98% |
| MyISAM | Full scan (ms) | 10.3507 ± 0.3222 | 15.5765 ± 2.7931 | +50.49% |
| MyISAM | Source aggregate (ms) | 0.2524 ± 0.0137 | 0.3036 ± 0.0492 | +20.29% |
| MEMORY | Load (s) | 0.6906 ± 0.0410 | 0.8276 ± 0.0864 | +19.83% |
| MEMORY | Point lookup (ms) | 0.2337 ± 0.0073 | 0.2325 ± 0.0485 | -0.49% |
| MEMORY | Full scan (ms) | 5.7458 ± 0.3325 | 8.0415 ± 0.8136 | +39.95% |
| MEMORY | Source aggregate (ms) | 0.2080 ± 0.0119 | 0.1777 ± 0.0476 | -14.61% |
| ROCKSDB | Load (s) | 1.2440 ± 0.0182 | 1.3527 ± 0.1675 | +8.74% |
| ROCKSDB | Point lookup (ms) | 0.2491 ± 0.0079 | 0.2673 ± 0.0474 | +7.32% |
| ROCKSDB | Full scan (ms) | 18.8477 ± 0.3985 | 26.6262 ± 1.1715 | +41.27% |
| ROCKSDB | Source aggregate (ms) | 0.2578 ± 0.0197 | 0.2534 ± 0.0208 | -1.72% |

Cloud load means were **8.56–31.17% longer**, and full scans **37.18–50.49% longer**,
than the archived laptop run. Point lookup and source-aggregate differences are mixed.
Cloud sample SDs are larger for all 20 engine/metric combinations. The point-lookup
and source-aggregate ordering changes, so short-query rankings should not be generalized.

The broad load/scan observations agree across these two environments: MEMORY has the
lowest mean load and scan times, MyISAM the lowest persistent-engine load, Aria the
highest mean load and the lowest persistent-engine scan, and ROCKSDB the highest mean
scan. These are observations for this small warm reference table. They do not remove
MEMORY's volatility or establish equal persistence guarantees between engines.
The original [laptop findings and charts](openflights-findings.md) remain the original
single-machine report; no historical numbers or recommendations were silently replaced.

## Environment, images and controls

| Item | Cloud reproduction | Original laptop context |
| --- | --- | --- |
| Execution | Managed virtualized Linux amd64; Debian 13 executor; nested Docker/vfs | Windows 11 / Docker Desktop WSL2; [October 9 host snapshot](benchmark-environment.md) |
| Kernel / visible CPUs | `6.18.57`; 3 visible CPUs | `6.18.40.1-microsoft-standard-WSL2`; 12 visible CPUs in runner metadata |
| CPU/RAM context | Later read-only snapshot: virtual CPU model Intel Xeon Platinum 8573C, Docker-visible memory 10,452,459,520 bytes | Ryzen 5 7530U; Windows-visible 15.4 GiB and Docker-visible 8,000,094,208 bytes in the dated snapshot |
| Docker / Compose | Engine 28.4.0 / Compose 2.40.3 | Engine 29.8.0 / Compose 5.5.1 in the dated snapshot |
| Server / runner | MariaDB 11.8.9; Python 3.12.15; PyMySQL 1.1.2 | Same versions recorded in the original results |
| Quotas | DB 2 CPU / 2 GiB; runner 1 CPU / 512 MiB | Same configured quotas; quotas do not reserve physical cores |
| SQL controls | Strict/no-substitution; query cache OFF; autocommit ON; session MEMORY max 128 MiB | Same recorded global/session settings |
| Power | Physical power/governor unavailable; no other benchmark containers running | `plugged in; battery saver off` |

[Supplemental host fields](../evidence/reproductions/20261030-cloud-linux-openflights/post-run-host.json)
were captured after measurements, with an explicit observation time. They do not prove
physical-host allocation or historical scheduling/thermal conditions. Per-run JSON is
the source for contemporaneous runner and database controls. The laptop host snapshot
also cannot reconstruct every historical hardware/runtime condition.

Cloud build identities were recorded before the pilot:

- DB: `sha256:773c1c3f993470230c89b7d8752ea1d4a5b2bd561fd7084094a8b0d0fffe7839`.
- Runner: `sha256:ab7bb291c1122c3ef48c033fb6e0b6c8cceaffdd04136fa78613f01b3a88b40d`.

The [image record](../evidence/reproductions/20261030-cloud-linux-openflights/runtime-provenance.json)
and [database controls](../evidence/reproductions/20261030-cloud-linux-openflights/db-controls.txt)
retain their scope. The actual DB image is verified. The recorded command sequence has
no rebuild, pull or settings change between pilot and full, but OpenFlights used Compose
tags rather than enforcing immutable IDs, and the removed runner containers have no
retained per-run image inspections. Do not infer stronger image-drift protection from
the separate cache-pressure/write-diagnostic controls or claim the laptop image is identical.

External [build adapters](../evidence/reproductions/20261030-cloud-linux-openflights/build/)
mount the cloud CA as a build secret for pip/apt trust and make copied files readable
because checkout files have private permissions. The repository Dockerfiles remain unchanged.
Only the fresh disposable results directory was made writable for UID 10001. Base/layer
build cache was reused; this was fresh checkout/credential/volume setup, not a cold image build.
No TLS, dataset-hash or package-signature verification was disabled.

## Commands and independent rechecking

The [command record](../evidence/reproductions/20261030-cloud-linux-openflights/commands.json)
contains the executed setup, pilot/full and stop invocations. All Compose commands used
`-p cu-repro-20261030` and the same external build adapter. The pilot completed and was
reviewed before full. Setup/test and benchmark transcripts are archived separately.
The database was stopped cleanly; the existing `cu-engine-lab_db_data` and new
`cu-repro-20261030_db_data` volumes remain intact. No environment settings were modified
or republished.

From a checkout containing this archive, these offline commands validate the pinned
dataset, all four runs, comparison JSON/CSV and archived file checksums. They require
standard-library Python, no running Docker and no reporting/plotting dependencies:

```bash
python3 scripts/fetch_openflights.py
python3 evidence/reproductions/20261030-cloud-linux-openflights/validate.py
python3 -O evidence/reproductions/20261030-cloud-linux-openflights/validate.py
```

The fetcher works offline if the pinned file already exists. The validator makes no
database changes; its explicit `--write` option only regenerates comparison JSON/CSV
and is intended for archive maintenance before checksums are sealed. Validation preserves
all archived data. [Preservation metadata](../evidence/reproductions/20261030-cloud-linux-openflights/preservation.json)
records the baseline Git trees and counts of historical files checked byte-for-byte.

## Limits and pending teammate evidence

This demonstrates a second environment's successful fresh setup and complete OpenFlights
workload, not identical timings on a second laptop. Shared host scheduling, virtualization,
storage/vfs, image build history and physical hardware differ. The run cannot isolate an
OS effect or validate the original laptop's absolute latency. Trials reuse a server and
its caches; five rounds give limited variability information. Reads are warm, client/network
time is included, cache/durability budgets are not equalized, and 67,663 rows may fit in cache.
No cold-cache, physical-disk, steady-state compaction or power-loss result follows.

This reproduction sequence did not rerun the stock tutorial or the all-report checker
before measuring; earlier [maintenance validation](maintenance-validation.md) is separate.
During archival, `scripts/check_reports.py --repeat` additionally passed on the publishing
checkout: all eight historical reports regenerated twice, 55 outputs validated and
inputs preserved. Its [post-run transcript](../evidence/reproductions/20261030-cloud-linux-openflights/logs/archive-report-check.txt)
is separate from the measurement-time setup checks.
Zane's pending physical-laptop package is expected to include independent setup,
stock tutorial/transaction checks, repeated report regeneration, pilot/full evidence,
actual conditions/images and a readable transcript under his own fixed tested revision.
His prompt also requests immutable image selection for OpenFlights. Attribute those
future results to him when received and validated; this cloud run does not complete or
replace that contribution. A later documentation review can check instruction clarity.
