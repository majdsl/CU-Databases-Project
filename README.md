A project for area 6, "Choosing the right storage engine" for the [MariaDB student database projects, 2026-09](https://mariadb.org/bachelor_hackathon_2026-09/).

# Digital Crew: choosing a MariaDB storage engine

We compare InnoDB, Aria, MyISAM, MEMORY and MyRocks on MariaDB 11.8.9.
Start with a four-engine SQL demonstration; explore the repeated five-engine
measurements when you want the full experimental workflow.

## Start here

Install **Git, Python 3.9+ and Docker**, then start Docker with Linux containers
(amd64 or ARM64). From a terminal, run each line separately:

```powershell
git clone --branch main https://github.com/majdsl/CU-Databases-Project.git
cd CU-Databases-Project
python scripts/check_stock_tutorial.py
```

On Linux/macOS, use `python3` instead of `python`. Already cloned? Run the last
command from your checkout. Expect **`STOCK TUTORIAL PASS: amd64`** or **`arm64`**,
then `Saved: ...`. Open that directory's **`transcript.txt`** to read the SQL
observations; `validation.json` records the checked results and source hashes.

**What you will see:** all four tables start with 50,000 rows. After a server
restart, MEMORY is empty while InnoDB, Aria and MyISAM retain their rows.

This **Path B** uses a pinned official image and a disposable database. It checks
indexes, concurrent updates, rollback, restart persistence and cleanup on InnoDB,
Aria, MyISAM and MEMORY. The server has a 1 GiB memory limit; allow extra room for
Docker and image downloads. The command needs internet access on first use.
It uses host Python's standard library; the custom MyRocks build is a later path.
The temporary database is cleaned up while the transcript is retained.

Follow the [interactive SQL walkthrough](docs/tutorial.md#path-b-arm-laptops-or-a-quick-try-stock-image-four-engines)
to try the statements yourself, or read the [three measured lessons](docs/three-engine-lessons.md)
without installing anything. [Platform evidence and troubleshooting](docs/stock-tutorial-validation.md)
cover the tested Linux amd64/ARM64 and Windows Docker Desktop paths; a physical
macOS walkthrough is still pending. Tutorial checks demonstrate correctness;
performance conclusions use the separate repeated measurements below.

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

![Five repeated OpenFlights load trials per engine](docs/figures/openflights-load.png)

### Why the results differ

- **MEMORY:** HASH range queries scanned the table; BTREE used range access.
  The 100,000-row ten-row range took 13.52 times as long with HASH; both tables remain volatile.
- **MyRocks:** ZSTD cut repetitive table SST bytes by 95.15%, versus 0.44% for
  high-entropy values. These are flush-only file measurements, not a steady-state compaction result.
- **Aria:** table-lock waits appeared even for disjoint-row writers; the counters
  establish contention without assigning a share of runtime to waiting.

The [short article](docs/three-engine-lessons.md) explains the controls and practical
implications. The [decision guide](docs/engine-recommendations.md) covers
all five engines, with [cache/durability budgets](docs/cache-and-durability.md)
and [image-provenance limits](docs/image-provenance.md) kept explicit.

## Run one comparison and read the result

For the **five-engine Linux amd64** lab, follow the complete
[setup → pilot → inspect → full → stop → verify ZIP guide](docs/openflights-reproduction.md).
It includes native-Linux output permissions and preserves the setup database.
Full OpenFlights mode has 25 balanced trials; keep its results separate from pilots
and from other hosts. New files under `results/` stay local until archived or copied.
For inspection without a run, open the [archived full summary](evidence/openflights/20261009T160813Z-openflights-6884f225/summary.md).

## Data model and measurement method

| Dataset | Design | Reason |
| --- | --- | --- |
| Seeded synthetic flight events | Integer event key; route/time index; integer fare, delay and passenger fields; bounded high-entropy payload | Reproducible updates and integrity checks without monetary floating-point rounding |
| Pinned OpenFlights routes | Source-row key; nonunique source/destination index; nullable original IDs | Preserve repeated route combinations and missing IDs instead of silently dropping records |

Each engine receives the same rows, logical schema and query stream **within an experiment**.
The shared flight schemas declare BTREE explicitly to avoid MEMORY's default HASH
index as a confounder, and use utf8mb4_bin for consistent string comparison.
The separate integer-only index experiment
deliberately changes HASH versus BTREE.
Physical storage still differs. No foreign keys or engine-specific alternatives are added
to the common schema; this is not a complete airline application. See the
[synthetic schema rationale](docs/benchmark-method.md), [route transformation](docs/openflights-method.md)
and directly comparable [SQL schemas](sql/openflights/).

Every loaded row and query answer is verified. Read statistics use trial means
and sample SD across repeated rounds; driver/network time is included and validation
warms caches. These laptop repeats do not establish independent-host or OS effects.
Stopped-volume file sizes and process-restart survival are separately scoped;
see the methods for each experiment below.

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
| MyRocks compression on two controlled data profiles | [Isolated no-compression/ZSTD protocol](docs/rocksdb-compression-method.md) | [32-trial findings and charts](docs/rocksdb-compression-findings.md); [separate CI correctness](evidence/reviews/20261027-rocksdb-compression-ci/README.md) |


The [safe offline report checker](docs/report-reproducibility.md) regenerates eight
reports / 55 outputs in a temporary copy. [CI](docs/ci.md) checks both stock-image
architectures and the five-engine lab. [Environment](docs/benchmark-environment.md),
[setup troubleshooting](docs/setup.md) and the [project checkpoint](docs/project-checkpoint.md)
provide conditions and validation history.

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
the official evaluator. The [evidence plan](docs/evidence-plan.md) records the scope
of completed checks, historical review provenance and remaining reproduction work.

## License

The team's original project code and documentation are licensed under the
[MIT License](LICENSE).

The OpenFlights dataset and OpenFlights-derived data retain their
[ODbL 1.0 license](data/openflights/LICENSE) and
[source attribution](data/openflights/README.md). Third-party software, public
package inputs and externally sourced material keep their respective licenses;
the MIT license does not replace those terms.

References: [official assignment and rubric](https://mariadb.org/bachelor_hackathon_2026-09/),
[MariaDB engine documentation](https://mariadb.com/docs/server/server-usage/storage-engines).
