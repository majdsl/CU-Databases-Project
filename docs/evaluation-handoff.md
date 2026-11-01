# Fresh evaluation handoff

Repository: <https://github.com/majdsl/CU-Databases-Project>.
Submission branch: `main`. Area: **6, “Choosing the right storage engine”**.
Developed database: MariaDB 11.8.9, with InnoDB, Aria, MyISAM, MEMORY and MyRocks.

This is a factual source/evidence index for a new review. It supplies no proposed
score. Previous assessments are historical records, not a target or runtime evidence.

## Pin the evaluation target

The final starter message accompanying this handoff supplies the exact remote main
SHA after this documentation cleanup is merged. A fresh review records that SHA,
the branch, date and available tools before assessing it. From an existing clean
checkout, the remote target can be checked without changing source:

```sh
git fetch origin
git ls-remote origin refs/heads/main
git rev-parse origin/main
```

The two remote identities should agree. If main has advanced from the supplied
SHA, record that difference before selecting the target. Keep source/evidence
unchanged during assessment; fixes belong to a later task.

The completed implementation/validation baseline is
`3dfab238d5d34c6d63082b8273fbc63f47c03414` ([PR #15](https://github.com/majdsl/CU-Databases-Project/pull/15)).
This handoff and the checkpoint are later documentation changes. The baseline,
producing measurement SHAs and next evaluation target are distinct identities.

## Official criteria and references

- [Current assignment and evaluation prompt](https://mariadb.org/bachelor_hackathon_2026-09/),
  including Area 6 and its linked MariaDB documentation. The November 1 retrieval
  showed the prompt last updated **September 4, 2026**; the live page determines
  whether that has changed.
- Dated source copies: [official prompt](../evidence/evaluations/20261101-internal-review/official-evaluation-prompt.txt)
  and [Area 6](../evidence/evaluations/20261101-internal-review/official-area-6.txt).
  These are source snapshots, not a new assessment.
- [MariaDB Storage Engines reference](https://mariadb.com/docs/server/server-usage/storage-engines.md)
  and [reference retrieval identities](../evidence/evaluations/20261101-internal-review/reference-sources.json).

The official prompt determines criteria and output format. Unavailable required
sources or execution capabilities should be recorded explicitly.

## Reader and implementation entry points

| Topic | Repository paths |
| --- | --- |
| Findings, schema reasoning, recommendations and team | [README](../README.md), [engine recommendations](engine-recommendations.md), [team contributions](team-contributions.md) |
| Prerequisites and execution | [Setup](setup.md), [SQL tutorial](tutorial.md), [prepared OpenFlights workflow](openflights-reproduction.md) |
| Data and comparable schemas | [Pinned data manifest](../data/openflights/manifest.json), [fetcher](../scripts/fetch_openflights.py), [OpenFlights schemas](../sql/openflights/), [synthetic schemas](../sql/benchmark/) |
| Measurement method | [Baseline method](benchmark-method.md), [OpenFlights method](openflights-method.md), [environment](benchmark-environment.md), [cache/durability settings](cache-and-durability.md); README links the other experiment-specific methods/findings |
| Harness and guards | [Benchmarks](../benchmarks/), [lightweight tests](../tests/), [offline report/tutorial tests](../report-tests/), [CI workflow](../.github/workflows/correctness.yml) |
| Report regeneration | [Reproduction guide](report-reproducibility.md), [temporary-copy checker](../scripts/check_reports.py) |

## Execution evidence and its producing revisions

| Evidence | Identity and observed scope |
| --- | --- |
| [Completed baseline main CI](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324235736) | Success at `3dfab238d5d34c6d63082b8273fbc63f47c03414`: 146 lightweight/105 offline tests in normal and optimized Python; five-engine setup/integration and SQL tutorial; stock tutorials on native Linux amd64/ARM64. The optional timed full-session job was skipped. Newer revision checks must be identified separately. |
| [Actual complete OpenFlights workflow](https://github.com/majdsl/CU-Databases-Project/actions/runs/41321256187) | Success at frozen source `2da20124ca1e52128d7cb8c3536736ae139239f7`: five pilot trials, inspection, 25 full trials, clean stop, export, separate extraction and standalone verification. Shared-CI workflow validation. |
| [OpenFlights raw records and provenance](../evidence/reproductions/20261101-ci-openflights-session/README.md) | Session `20261101T152845Z-openflights-session-ba84d4b7`; pilot `20261101T152902Z-openflights-444900b0`; full `20261101T152915Z-openflights-8fa924ee`. Immutable images/controls, raw samples, build record and original export are retained. |
| [Historical laptop/OpenFlights findings](openflights-findings.md) and [October 30 cloud reproduction](openflights-linux-reproduction.md) | Separate producing revisions, machines, pilot/full files and statistics. The shared-CI workflow does not replace these measurements. |
| [Snapshot-build index](../evidence/reviews/20261101-snapshot-builds/README.md) | Three original attempts retain failed, incomplete and complete outcomes. Complete archived [run 41322953291](https://github.com/majdsl/CU-Databases-Project/actions/runs/41322953291) used PR merge `ab8cc6df8ac823011e9c797e86817d9d2f6ee568`. |
| [Baseline main paired-build check](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324235769) | Success at `3dfab238d5d34c6d63082b8273fbc63f47c03414`: two uncached signed-snapshot DB builds/readbacks/stops. Package inventories/configuration match; image/config and filesystem identities differ. |

### Original archives and integrity checks

- [OpenFlights export ZIP](../evidence/reproductions/20261101-ci-openflights-session/ci/openflights-evidence.zip),
  committed in Git: 87,843 bytes, SHA-256
  `2df17236c7f9ed91acded1525a1eb87ef04f756d40029ac01e1278ecf795c35a`.
- [Original snapshot artifact ZIPs on GitHub Releases](https://github.com/majdsl/CU-Databases-Project/releases/tag/evidence-reconstruction-20261101),
  with run/source/size/hash identities in [artifacts.json](../evidence/reviews/20261101-snapshot-builds/artifacts.json).
  The complete ZIP's SHA-256 is
  `e7f883ccc00b186e286c7dc7e8bc7640bf24beb95714e4981ed9a38ac418f995`.
  The [publication run](https://github.com/majdsl/CU-Databases-Project/actions/runs/41324256907)
  downloaded every uploaded asset again and checked its hash.

These existing-evidence checks do not launch Docker or execute SQL:

```sh
python3 evidence/reproductions/20261101-ci-openflights-session/verify.py
python3 evidence/reproductions/20261101-ci-openflights-session/recheck.py
python3 -O evidence/reproductions/20261101-ci-openflights-session/recheck.py
python3 evidence/reviews/20261101-snapshot-builds/verify.py
```

The standalone verifier checks complete byte integrity. Semantic rechecking
recalculates trial statistics/summaries and validates recorded session, image,
control, shutdown and export identities. Neither is fresh SQL execution or an
independent observation of the producing run. The snapshot Git index omits large
package-input tar files; the original release ZIPs retain them.

## Limits relevant to interpreting the evidence

- Shared-CI timings validate the workflow. They do not identify an OS effect or
  complete independent human/physical-laptop installation; that task remains pending.
- Current native ARM64 coverage is the four-engine stock tutorial. No new interactive
  Windows/macOS walkthrough or ARM64 five-engine lab run is claimed.
- Experiment-specific methods disclose warm reads/client overhead, unequal
  cache/durability budgets, bounded process-restart behavior and compression-study
  conditions. Broader durability or steady-state conclusions need separate evidence.
- A package inventory is not a complete dependency lock. The isolated snapshot
  candidate passed builds/readbacks but produced different image bytes; retention
  and adoption limits are in [build reconstruction](build-reconstruction.md).
- The missing historical assessment-chat ZIP remains unavailable; its claimed new
  measurements remain unverified. The two October 31 capacity failures ended before
  timed workloads and are not successful pilots.

The fresh evaluation should distinguish commands it actually executes from source,
archived results and CI it inspects. No fresh evaluation has been run as part of
preparing this handoff.
