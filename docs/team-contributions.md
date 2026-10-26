# Team and contributions

Constructor University database course, Fall 2026. The project combines benchmark
engineering, experimental execution, independent report checks, technical review
and a reusable SQL tutorial. The names and completed review activities below were
confirmed by the team through the repository owner. This page records their completed work
and supporting evidence.

**Status: all three team members have completed the contributions listed below.**
Any future improvements will be recorded as additional completed work.

| Team member | GitHub | Role |
| --- | --- | --- |
| Majd Salimoun | [majdsl](https://github.com/majdsl) | Technical Lead and Project Engineer |
| Hassan Kheder | [Hassan457-123](https://github.com/Hassan457-123) | Reproducibility and Quality Assurance Engineer |
| Zeineldin Mohamed Hassan | [zein-935](https://github.com/zein-935) | Evaluation Analyst and Tutorial Engineer |

## Majd Salimoun

**Role: Technical Lead and Project Engineer**

Majd coordinated the technical direction and delivered the platform, benchmark
harnesses and experimental analysis across the project's measurement workflow.

- **Technical Leadership and Project Engineering:** coordinated the technical
  direction, implementation sequence, experiment delivery and integration of the
  team's reviewed changes into the published project.
- **Database Platform and Five-Engine Integration:** built the MariaDB/Python
  environment, explicit comparable schemas, MyRocks plugin integration,
  engine-availability checks and controlled container settings.
- **Benchmark and Data Engineering:** implemented seeded data generation, repeatable
  workloads, balanced trial ordering, complete row/query verification, timing,
  telemetry, failure handling and checkpointed result capture.
- **Experimental Execution and Evidence Management:** carried out laptop setup and
  operation, pilot/full measurements, power-condition recording, result collection
  and publication of the baseline, concurrent-write/CPU, storage, recovery, OpenFlights,
  MEMORY-index, InnoDB cache-pressure and write-diagnostic evidence.
- **Statistical Analysis and Data Visualization:** developed trial-level statistics,
  uncertainty and scope checks, report generators, comparison figures and
  requirements-based engine recommendations grounded in the archived observations.
- **Reproducibility Engineering and CI Automation:** implemented version/image/source
  metadata, setup orchestration, reporting workflows, correctness checks and
  integration of the team's reviewed fixes.
- **Technical Documentation and Research Communication:** produced the methods,
  findings, setup instructions, evidence mapping and final presentation of the
  team's completed work, connecting measured trade-offs to practical engine choices.

Implementation, execution and analysis were AI-assisted. The [experiment index](../README.md#explore-or-reproduce-the-other-experiments),
[archived evidence](../evidence/), [report reproduction](report-reproducibility.md),
[setup](setup.md) and [CI](ci.md) provide the concrete outputs. Laptop commands and
archived measurements are distinct from hosted CI correctness tests.

## Hassan Kheder

**Role: Reproducibility and Quality Assurance Engineer**

Hassan contributed reproducibility assessment, reporting quality assurance and
visualization analysis. His review connected the archived data, generated outputs
and validation code, producing a concrete reporting fix and a repeatable test record.

- **Reproducibility Engineering:** ran all seven report generators with the
  documented reporting dependencies, repeated generation and checked that the
  numerical findings remained consistent.
- **Data Analysis and Integrity Assurance:** examined the generated statistics and
  figures against the stored evidence, with SHA-256 checks confirming that all
  714 evidence files in his reviewed snapshot retained their bytes.
- **Defect Analysis and Validation Hardening:** identified that optimized
  Python removed storage-report assertions, and replaced them with explicit
  validation failures for inconsistent row counts, checksums, shutdown records,
  file inventories and storage deltas.
- **Regression Test Engineering:** added six corrupted-evidence cases requiring
  failure before report output was created. His submitted 116-test snapshot passed
  in normal and optimized Python; the regression is now part of the offline CI suite.
- **Visualization Analysis and Refinement:** reviewed chart readability and the
  distinction between measurements and interpretation, and revised the MEMORY
  allocation legend to distinguish row data from index allocation clearly.
- **Technical Reporting and Review Handoff:** supplied the patch, test logs,
  reproduction commands and review notes, making the changes inspectable and
  straightforward to integrate and verify.

Published outputs: [named review](teammate-1-review.md),
[submitted test logs and provenance](../evidence/reviews/20261024-hassan/README.md),
[storage-report generator](../scripts/report_storage_findings.py),
[offline regression](../report-tests/test_storage_findings.py) and
[PR #3](https://github.com/majdsl/CU-Databases-Project/pull/3).
The maintainer independently reproduced the reports/tests and integrated the
report regression into the separate dependency-equipped CI job.

## Zeineldin Mohamed Hassan

**Role: Evaluation Analyst and Tutorial Engineer**

Zeineldin contributed evaluation analysis, experiment and documentation review,
and the hands-on tutorial. His work connected the measured results to the assignment
criteria and to practical SQL examples a reader can follow and reuse.

- **Evaluation and Rubric Analysis:** reviewed the repository with the published
  MariaDB evaluation, identified opportunities for improvement and communicated
  criterion-level feedback to guide the team's revisions.
- **Experimental Design and Method Review:** reviewed the experimental choices,
  comparable schemas and workloads, and the relationship between the measured
  evidence and the conclusions presented to readers.
- **Data Evaluation and Mechanism Interpretation:** reviewed the reported engine
  trade-offs and explained how index access, table locking, restart volatility
  and storage metadata relate to the project's observed results.
- **Technical Documentation and Learning Design:** checked and revised the
  documentation, added the README tutorial entry point, and organized a coherent
  setup-to-SQL-to-interpretation path with links to the measured findings.
- **SQL Tutorial Engineering:** authored the initial walkthrough and seven
  SQL scripts covering comparable engine schemas, generated data, MyRocks setup,
  engine metadata, MEMORY HASH/BTREE plans, concurrent writes, restart persistence
  and cleanup.
- **Review Synthesis and Project Refinement:** brought evaluation findings
  back to the team, including the need to evaluate `main`, and helped connect
  documentation improvements to the project's experimental objectives.

Published outputs: [hands-on tutorial](tutorial.md),
[original SQL tutorial commit](https://github.com/majdsl/CU-Databases-Project/commit/f4c5696667108c0497c09bba572cc1f6d264a5e5),
[PR #4](https://github.com/majdsl/CU-Databases-Project/pull/4),
[named review](teammate-2-review.md) and
[received evaluation response](../evidence/evaluations/20261026-team-review-35/README.md).
The later source corrections and automated tutorial validation are documented
as maintainer integration work, preserving the attribution of his original tutorial.

## Completed contributions and shared workflow

Majd's platform and benchmark engineering, Hassan's reproducibility and reporting
quality assurance, and Zeineldin's evaluation and tutorial development are complete
and documented through the outputs linked above. Further improvements can extend
this record as they are delivered.

AI assistance was used in development, analysis, debugging and review. Team credit
reflects responsibility for producing, running, checking and integrating the work;
commit counts alone do not describe all review and experimental contributions.
The original measurements and historical source metadata are preserved. Tutorial
SQL demonstrations and mock-based unit output are not new performance observations.

Hassan's recorded reproduction validates archived reports; hosted tutorial checks
validate Linux amd64 SQL correctness. The [evidence plan](evidence-plan.md) describes
the scope of these checks. The [35/40 practice-evaluation follow-up](evaluation-follow-up.md)
tracks project-level feedback and possible extensions separately from this completed
team record.
