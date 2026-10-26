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

Hassan reproduced all seven reports from archived data, reviewed their numerical
outputs and figures, and contributed a storage-report validation fix with six
corrupted-evidence regression cases. The fix prevents optimized Python from removing
row-count, checksum, shutdown, inventory and delta checks. He revised the MEMORY
allocation legend and supplied normal/optimized test logs.

The [named review](teammate-1-review.md), [submitted logs and provenance](../evidence/reviews/20261024-hassan/README.md)
and [PR #3](https://github.com/majdsl/CU-Databases-Project/pull/3) document this work.
The maintainer independently reran the reports and tests and adapted the regression
for the separate offline CI job. Hassan's contribution is archived-report
reproduction, testing, debugging and visualization review; it is not presented as a
new Docker benchmark or independent-machine performance measurement.

## Zeineldin Mohamed Hassan

Zeineldin reviewed the project against the published evaluation, checked
and revised documentation, reviewed experiment design and interpreted the reported
data. These completed review activities were confirmed by the repository owner.
He also authored the hands-on SQL tutorial, connecting five-engine table creation,
engine metadata, MEMORY index plans, concurrent locking and restart persistence to
the measured reports.

The [tutorial](tutorial.md), original [PR #4](https://github.com/majdsl/CU-Databases-Project/pull/4),
[authored commit](https://github.com/majdsl/CU-Databases-Project/commit/f4c5696667108c0497c09bba572cc1f6d264a5e5)
and [review record](teammate-2-review.md) document the contribution. Later tutorial
corrections and automated CI validation are identified separately from his original
commit. The newest evaluation was reported as 33/40; its full text, model/tool
context and evaluated revision have not yet been archived, so no criterion scores
or explanations are inferred from that total.

## Shared workflow and remaining evidence

AI assistance was used in development, analysis, debugging and review. Team credit
reflects responsibility for producing, running, checking and integrating the work;
commit counts alone do not describe all review and experimental contributions.
The original measurements and historical source metadata are preserved. Tutorial
SQL demonstrations and mock-based unit output are not new performance observations.

The confirmed roster is complete. Remaining evidence concerns are the full latest
evaluation, any separate manual tutorial/reproduction transcript, and the broader
limitations in the [evidence plan](evidence-plan.md). No official grade is claimed.
