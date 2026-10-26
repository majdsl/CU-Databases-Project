# Team and contributions

Constructor University database course, Fall 2026. The project combines benchmark
engineering, experimental execution, independent report checks, technical review
and a reusable SQL tutorial. The names and completed review activities below were
confirmed by the team through the repository owner. This page records responsibilities
and supporting evidence.

| Team member | GitHub | Role |
| --- | --- | --- |
| Majd Salimoun | [majdsl](https://github.com/majdsl) | Technical Analyst — Benchmark Engineering and Experimental Analysis |
| Hassan Kheder | [Hassan457-123](https://github.com/Hassan457-123) | Reproducibility, Validation and Visualization Review |
| Zeineldin Mohamed Hassan | [zein-935](https://github.com/zein-935) | Evaluation, Method Review and Tutorial Development |

## Majd Salimoun

Majd's contribution spans the project's implementation and experimental workflow:

- **Five-engine integration:** the MariaDB/Python environment, explicit comparable
  schemas, MyRocks plugin integration, engine-availability checks and controlled
  container settings.
- **Benchmark design and implementation:** seeded data generation, repeatable
  workloads, balanced trial ordering, complete row/query verification, timing,
  telemetry, failure handling and checkpointed result capture.
- **Experimental execution and evidence management:** laptop setup and operation,
  pilot/full measurements, power-condition recording, result collection and
  publication of the baseline, concurrent-write/CPU, storage, recovery, OpenFlights,
  MEMORY-index and InnoDB cache-pressure evidence.
- **Results analysis and visualization:** trial-level statistics, uncertainty and
  scope checks, report generators, comparison figures and requirements-based engine
  recommendations grounded in the archived observations.
- **Reproducibility tooling and CI automation:** version/image/source metadata,
  setup orchestration, reporting workflows, correctness checks and integration of
  the team's reviewed fixes.
- **Technical documentation and project coordination:** methods, findings, setup
  instructions, evidence mapping, review integration and final presentation of the
  team's completed work.

Implementation, execution and analysis were AI-assisted. The [experiment index](../README.md#explore-or-reproduce-the-other-experiments),
[archived evidence](../evidence/), [report reproduction](report-reproducibility.md),
[setup](setup.md) and [CI](ci.md) provide the concrete outputs. Laptop commands and
archived measurements are distinct from hosted CI correctness tests.

## Hassan Kheder

Hassan contributed reproducibility assessment, reporting quality assurance and
visualization analysis. His review connected the archived data, generated outputs
and validation code, producing a concrete reporting fix and a repeatable test record.

- **Archived-report reproduction:** ran all seven report generators with the
  documented reporting dependencies, repeated generation and checked that the
  numerical findings remained consistent.
- **Data analysis and integrity review:** examined the generated statistics and
  figures against the stored evidence, with SHA-256 checks confirming that all
  714 evidence files in his reviewed snapshot retained their bytes.
- **Defect diagnosis and corrective implementation:** identified that optimized
  Python removed storage-report assertions, and replaced them with explicit
  validation failures for inconsistent row counts, checksums, shutdown records,
  file inventories and storage deltas.
- **Regression testing:** added six corrupted-evidence cases requiring failure
  before report output was created. His submitted 116-test snapshot passed in
  normal and optimized Python; the regression is now part of the offline CI suite.
- **Visualization review and refinement:** reviewed chart readability and the
  distinction between measurements and interpretation, and revised the MEMORY
  allocation legend to distinguish row data from index allocation clearly.
- **Reproducibility documentation and handoff:** supplied the patch, test logs,
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

Zeineldin contributed evaluation analysis, experiment and documentation review,
and the hands-on tutorial. His work connected the measured results to the assignment
criteria and to practical SQL examples a reader can follow and reuse.

- **Evaluation and criteria analysis:** reviewed the repository with the published
  MariaDB evaluation, identified opportunities for improvement and communicated
  criterion-level feedback to guide the team's revisions.
- **Experiment and design review:** reviewed the experimental choices, comparable
  schemas and workloads, and the relationship between the measured evidence and
  the conclusions presented to readers. The repository owner confirmed this
  completed review activity.
- **Data evaluation and interpretation:** reviewed the reported engine trade-offs
  and explained how index access, table locking, restart volatility and storage
  metadata relate to the project's observed results.
- **Technical documentation and reader guidance:** checked and revised the
  documentation, added the README tutorial entry point, and organized a coherent
  setup-to-SQL-to-interpretation path with links to the measured findings.
- **Hands-on SQL tutorial development:** authored the initial walkthrough and seven
  SQL scripts covering comparable engine schemas, generated data, MyRocks setup,
  engine metadata, MEMORY HASH/BTREE plans, concurrent writes, restart persistence
  and cleanup.
- **Review communication and project refinement:** brought evaluation findings
  back to the team, including the need to evaluate `main`, and helped connect
  documentation improvements to the project's experimental objectives.

Published outputs: [hands-on tutorial](tutorial.md),
[original SQL tutorial commit](https://github.com/majdsl/CU-Databases-Project/commit/f4c5696667108c0497c09bba572cc1f6d264a5e5),
[PR #4](https://github.com/majdsl/CU-Databases-Project/pull/4),
[named review](teammate-2-review.md) and
[received evaluation response](../evidence/evaluations/20261026-team-review-35/README.md).
The later source corrections and automated tutorial validation are documented
as maintainer integration work, preserving the attribution of his original tutorial.

## Shared workflow and remaining evidence

AI assistance was used in development, analysis, debugging and review. Team credit
reflects responsibility for producing, running, checking and integrating the work;
commit counts alone do not describe all review and experimental contributions.
The original measurements and historical source metadata are preserved. Tutorial
SQL demonstrations and mock-based unit output are not new performance observations.

The confirmed roster and completed contributions are recorded. The latest supplied
practice evaluation is [archived as 35/40](evaluation-follow-up.md); its exact evaluated
revision and model/tool context remain to be supplied. Separate manual reproduction
transcripts and broader limitations remain in the [evidence plan](evidence-plan.md).
Hassan's recorded reproduction concerns archived reports; hosted tutorial checks
concern Linux amd64 SQL correctness. Neither is presented as new independent-machine
performance evidence. Further completed contributions can be appended with their
outputs and validation records. No official grade is claimed.
