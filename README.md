A project for area 6, "Choosing the right storage engine" for the [MariaDB student database projects, 2026-09](https://mariadb.org/bachelor_hackathon_2026-09/).

# CU Databases Project: choosing a storage engine

We use Python and MariaDB 11.8.9 to compare **InnoDB, Aria, MyISAM, MEMORY and MyRocks**
(SQL engine name `ROCKSDB`). The project measures load/read performance, concurrent
updates, storage allocation and acknowledged-row survival after process restarts.
The runnable code, raw evidence and reports are on `main`.

## Which engine, and what does it cost?

| Engine | OpenFlights load (s) | OpenFlights scan (ms) | Synthetic disk growth (MiB) | Starting recommendation |
| --- | ---: | ---: | ---: | --- |
| InnoDB | 1.1840 ± 0.0383 | 11.4745 ± 0.4860 | 9.129 | Transactional application data; largest measured small-table growth |
| Aria | 2.0078 ± 0.0305 | 9.7694 ± 0.4150 | 3.730 | Persistent non-transactional reference scans; slower loading here |
| MyISAM | 0.7932 ± 0.0213 | 10.3507 ± 0.3222 | 1.266 | Rebuildable loading-focused workloads; crash-table warnings in every forced trial |
| MEMORY | 0.6906 ± 0.0410 | 5.7458 ± 0.3325 | 0.121 overhead only | Rebuildable RAM cache; every tested restart emptied its rows |
| ROCKSDB | 1.2440 ± 0.0182 | 18.8477 ± 0.3985 | 1.168 | Investigate storage-constrained workloads; slowest scan here |

Read/load values are mean ± sample SD across **five trials of 67,663 real routes**.
Disk growth comes from a **separate 10,000-row synthetic experiment**, includes logs and
restart effects, and is not bytes per route. MEMORY's separate live allocation was
8.725 MiB for that synthetic table. The four persistent engines preserved all 1,000
acknowledged rows in each tested clean/forced restart; this does not prove power-loss
durability or transactional equivalence.

### Why the results differ

| Engine / mechanism | What our evidence shows | Interpretation boundary |
| --- | --- | --- |
| **InnoDB:** clustered B-tree pages, transactional logging and a buffer pool | Largest small-table datadir growth here; tables exceeding the fixed pool generated read activity | Page/log allocation and cache capacity matter; we did not isolate the cost of each durability feature. |
| **Aria:** table-level writes and crash-safe PAGE/log options | Concurrent writers waited even on different rows, with little gain from two to four clients | Lock counters support observed contention; read timings do not isolate its page-cache design. |
| **MyISAM:** separate data/index storage, table locks and no transactions | Fast persistent-engine loading here; table waits and forced-restart warnings were recorded | Loading speed does not supply transactional safety or eliminate a recovery/repair burden. |
| **MEMORY:** RAM-resident rows with HASH or BTREE indexes | Rows vanished on restart; HASH range queries scanned while BTREE used range access | Volatility and index access were demonstrated; all flight-read engines were warm, so fast reads alone do not isolate disk avoidance. |
| **MyRocks:** LSM organization, compression and compaction | Smallest persistent datadir growth and slowest OpenFlights scan mean here | Those observations do not isolate compression or compaction as their cause; short runs are not steady-state evidence. |

The [index](docs/memory-index-findings.md), [cache-pressure](docs/cache-pressure-findings.md)
and [lock-counter](docs/write-diagnostics-findings.md) experiments test specific
mechanisms. The [cache/durability inventory](docs/cache-and-durability.md) explains
why matching configured cache sizes does not equalize total memory or guarantees.

**Image provenance:** the cache-pressure and write-diagnostic orchestrators rebuild
at the start of each invocation, so pilot and full runs selected separately built
images. Their recorded source/settings/runtime matched, but image IDs differed.
The archived records do not identify which image bytes or metadata changed; pilot
and full statistics stay separate. See the [recorded identities and limits](docs/image-provenance.md).

See the [decision guide](docs/engine-recommendations.md) for requirements, mechanisms
and evidence. There is no universal winner. In the [CPU diagnostic](docs/cpu-findings.md),
changing the load generator's quota substantially changed throughput, demonstrating
why client limits must be checked before judging engine scaling.

A separate [MEMORY index experiment](docs/memory-index-findings.md) changes only HASH
versus BTREE: at 100,000 rows, the 10-row range took 13.52 times as long with HASH.
Plans and counters showed a table scan versus index-range access; equality means
were similar. This is a scoped mechanism result, not a new five-engine ranking.

![OpenFlights load measurements: individual trials and sample SD](docs/figures/openflights-load.png)

## Start here

**Hands-on tutorial:** Follow the [storage-engine tutorial](docs/tutorial.md) to create tables on five engines, compare their behavior, and test locking and restart persistence.

For a separate four-engine stock-image check, run
`python scripts/check_stock_tutorial.py` after cloning (use `python3` on Linux).
It creates and removes its own temporary database and saves a validation transcript.
See [Path B validation on native Linux amd64/ARM64 and Windows Docker Desktop](docs/stock-tutorial-validation.md).

To explore without installing anything, read the [full OpenFlights summary](evidence/openflights/20261009T160813Z-openflights-6884f225/summary.md)
and [findings](docs/openflights-findings.md), then the [decision guide](docs/engine-recommendations.md).

To run the project, install **Git, Python 3.9+ and Docker with Compose**, start Docker,
and use **Linux amd64 containers**. Windows Docker Desktop and Ubuntu amd64 are the
primary paths. Initial setup needs internet access. The DB/runner limits are 2 GiB/512 MiB;
allow extra memory for Docker and builds. For Linux permissions, ARM limitations,
manual steps and troubleshooting, see [setup details](docs/setup.md).

For a new checkout:

```powershell
git clone --branch main https://github.com/majdsl/CU-Databases-Project.git
cd CU-Databases-Project
python scripts/setup_project.py
```

After cloning, **setup is one command**. On Linux use `python3 scripts/setup_project.py`.
The wrapper verifies Docker, preserves/creates local credentials, fetches checksum-verified
data, builds containers, checks result-write permissions, runs unit tests and checks
all five actual engines. Success ends with **`SETUP PASS`**. Stop on errors.
Setup runs no benchmark and never deletes volumes. It can recreate this lab's container,
so do not run it during active measurements.

Keep `.env` private and unchanged for an existing database. A second clone shares the
normal Compose project name; it is not automatically an isolated database.
Stop the lab with `docker compose stop` to preserve data.

## Run one comparison and read the result

Keep power conditions stable and replace the label with your actual settings:

```powershell
docker compose run --rm runner python -m benchmarks.openflights --pilot --power-condition "plugged in; battery saver off"
```

Expect five engine trials and a summary marked **PILOT**. Every loaded row and query
answer is checked. The saved container path `/results/<run-id>` maps to
`results/<run-id>` in your checkout. Open `summary.md`; retain `results.json` for the
raw samples, checksums, query plans and runtime/settings metadata. One pilot round cannot
estimate variability. Investigate partial/failed output before proceeding.

After reviewing the pilot:

```powershell
docker compose run --rm runner python -m benchmarks.openflights --full --power-condition "plugged in; battery saver off"
```

This runs 25 trials, placing each engine once in each position over five rounds.
Timings on another machine need not be identical. Compare the conditions and variation,
and keep pilot observations separate from full-run statistics.

**Worked interpretation:** MEMORY loaded the archived route table in 0.6906 ± 0.0410 s,
versus InnoDB's 1.1840 ± 0.0383 s. That advantage can help a rebuildable cache.
Our separate restart test lost all MEMORY rows even after clean shutdown, so speed alone
does not justify using it for the only copy of authoritative data. The linked reports
show all trials and qualify each conclusion.

## Data model and measurement method

| Dataset | Design | Reason |
| --- | --- | --- |
| Seeded synthetic flight events | Integer event key; route/time index; integer fare, delay and passenger fields; bounded high-entropy payload | Reproducible updates and integrity checks without monetary floating-point rounding |
| Pinned OpenFlights routes | Source-row key; nonunique source/destination index; nullable original IDs | Preserve repeated route combinations and missing IDs instead of silently dropping records |

Each engine receives the same rows, logical schema and query stream **within an experiment**.
The shared flight schemas use explicit BTREE declarations and utf8mb4_bin to avoid
MEMORY's default HASH index as a confounder. The separate integer-only index experiment
deliberately changes HASH versus BTREE.
Physical storage still differs. No foreign keys or engine-specific alternatives are added
to the common schema; this is not a complete airline application. See the
[synthetic schema rationale](docs/benchmark-method.md), [route transformation](docs/openflights-method.md)
and directly comparable [SQL schemas](sql/openflights/).

The harness verifies the actual engine, checks every loaded value and validates query
answers. Verification warms caches. Timings include driver/network work; read statistics
summarize trial means, not pooled queries. The flight comparisons use five repeats; the MEMORY index comparison uses six.
These are repeats on one laptop, not independent machines. [Recorded cache and durability settings](docs/cache-and-durability.md) explain why
equal configured cache sizes are not equal total memory or durability guarantees.

Storage uses stopped-server inventories on fresh volumes. Recovery uses clean versus
SIGKILL restarts between acknowledged statements, with the host/cache still running.
Neither test establishes physical SSD footprint, device power-loss behaviour, interrupted
transactions or steady-state MyRocks compaction.

## Explore or reproduce the other experiments

| Question | Method and commands | Findings and evidence |
| --- | --- | --- |
| Synthetic loading and warm reads | [Baseline](docs/benchmark-method.md) | [Original baseline](evidence/baseline/20260923T121610Z-92b1c313/README.md) |
| Concurrent updates and client CPU limits | [Concurrency](docs/concurrency-method.md), [CPU diagnostic](docs/cpu-diagnostic.md) | [CPU findings](docs/cpu-findings.md) |
| Concurrent writes with database CPU and lock counters | [Isolated write diagnostic](docs/write-diagnostics-method.md) | [CPU and lock-wait findings](docs/write-diagnostics-findings.md) |
| Persistent allocation versus live RAM | [Storage procedure](docs/storage-method.md) | [Storage findings](docs/storage-findings.md) |
| Rows surviving clean/process-crash restarts | [Isolated recovery procedure](docs/recovery-method.md) | [Recovery findings](docs/recovery-findings.md) |
| InnoDB table size versus buffer pool | [Isolated cache-pressure protocol](docs/cache-pressure-method.md) | [Cache-pressure findings and charts](docs/cache-pressure-findings.md) |
| MEMORY index access paths | [HASH versus BTREE protocol](docs/memory-index-method.md) | [Index findings and charts](docs/memory-index-findings.md) |
| Real route data and secondary-index queries | [OpenFlights](docs/openflights-method.md) | [Route findings](docs/openflights-findings.md) |
| MyRocks compression on two controlled data profiles | [Isolated no-compression/ZSTD protocol](docs/rocksdb-compression-method.md) | Harness/CI correctness path; laptop pilot/full findings pending |

Read reports without rerunning experiments. The storage/recovery harnesses use isolated
temporary projects; never manually crash the normal lab database. Failed trials preserve
diagnostic evidence. The historical route snapshot is OpenFlights data, via MariaDB/openflights,
under [ODbL 1.0](data/openflights/LICENSE); its [download manifest](data/openflights/manifest.json)
pins the source and checksum. Synthetic events are complementary generated data, not real flights.

Seven report generators cover 28 chart files, including index, buffer-pool and lock-wait evidence. See
[report reproduction commands and checks](docs/report-reproducibility.md).
CI uses fresh containers and runs unit tests, real five-engine checks and a
stock-image tutorial on native Linux amd64 and ARM64;
see [CI scope](docs/ci.md). Performance measurements stay on controlled machines.
The [laptop record](docs/benchmark-environment.md), [runner image pin](docs/runner-image.md)
and [setup details](docs/setup.md) document versions and remaining environment limits.

## Team and completed contributions

Constructor University database course, Fall 2026.

**All three team members have completed the contributions recorded below.**
Future improvements can be added to this completed record.

### Majd Salimoun

**Technical Lead and Project Engineer** · [majdsl](https://github.com/majdsl)

- **Technical Leadership and Project Engineering:** coordinated implementation,
  experiments and integration of the team's reviewed changes.

- **Database Platform and Five-Engine Integration:** built the MariaDB/Python
  environment and integrated InnoDB, Aria, MyISAM, MEMORY and MyRocks.

- **Benchmark and Data Engineering:** implemented seeded workloads, balanced trial
  ordering and complete row/query verification.

- **Experimental Execution and Evidence Management:** executed pilot/full
  measurements and preserved the raw results and runtime metadata.

- **Statistical Analysis and Data Visualization:** produced trial-level statistics,
  comparison charts and evidence-based engine recommendations.

- **Reproducibility Engineering and CI Automation:** automated setup, reporting
  workflows and correctness checks.

- **Technical Documentation and Research Communication:** wrote methods, findings,
  setup instructions and the project's evidence guide.

### Hassan Kheder

**Reproducibility and Quality Assurance Engineer** · [Hassan457-123](https://github.com/Hassan457-123)

- **Reproducibility Engineering:** reproduced all seven archived reports and
  checked that repeated generation preserved the numerical findings.

- **Data Analysis and Integrity Assurance:** reviewed statistics and figures;
  verified SHA-256 integrity of all 714 evidence files in his reviewed snapshot.

- **Defect Analysis and Validation Hardening:** diagnosed and repaired storage-report
  validation that disappeared under optimized Python.

- **Regression Test Engineering:** added six corrupted-evidence cases and passed
  the submitted test suite with normal and optimized Python.

- **Visualization Analysis and Refinement:** reviewed chart readability and
  clarified the MEMORY allocation legend.

- **Technical Reporting and Review Handoff:** supplied the patch, test logs,
  reproduction commands and review notes.

[Hassan's completed review and evidence](docs/teammate-1-review.md).

### Zeineldin Mohamed Hassan

**Evaluation Analyst and Tutorial Engineer** · [zein-935](https://github.com/zein-935)

- **Evaluation and Rubric Analysis:** ran the published evaluation prompt and
  reported criterion-level feedback.

- **Experimental Design and Method Review:** reviewed comparable schemas,
  workload choices and the connection between evidence and conclusions.

- **Data Evaluation and Mechanism Interpretation:** reviewed engine trade-offs,
  index access, table locking and restart persistence.

- **Technical Documentation and Learning Design:** revised reader guidance and
  connected setup, SQL examples and measured findings.

- **SQL Tutorial Engineering:** authored the initial walkthrough and seven SQL
  scripts demonstrating engine behavior.

- **Review Synthesis and Project Refinement:** communicated evaluation findings,
  including the need to assess `main`, to guide improvements.

[Zeineldin's completed review and evidence](docs/teammate-2-review.md).

See [team contributions and supporting evidence](docs/team-contributions.md) for
completed work, AI assistance, linked commits/reviews and the limits of each check.
Follow-up changes use branches and pull requests into `main`, the branch read by
the official evaluator. The [received 35/40 practice evaluation and follow-up](docs/evaluation-follow-up.md)
track project-level feedback and possible extensions. Evaluation provenance and
the scope of the recorded checks are documented in the [evidence plan](docs/evidence-plan.md).

References: [official assignment and rubric](https://mariadb.org/bachelor_hackathon_2026-09/),
[MariaDB engine documentation](https://mariadb.com/docs/server/server-usage/storage-engines).
