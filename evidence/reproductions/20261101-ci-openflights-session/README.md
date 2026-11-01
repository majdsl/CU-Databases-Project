# Complete format-v2 OpenFlights workflow — November 1, 2026

**Successful shared-CI workflow validation; not controlled laptop performance.**
[Correctness run 41321256187](https://github.com/majdsl/CU-Databases-Project/actions/runs/41321256187)
passed all five jobs at frozen source
`2da20124ca1e52128d7cb8c3536736ae139239f7`. The measurement checkout was clean
and unchanged from preparation through export. The default working Dockerfiles
were used without a build adapter. Historical laptop/cloud archives remain untouched.

## Exact run identities

| Record | Identity |
| --- | --- |
| Session | `20261101T152845Z-openflights-session-ba84d4b7` |
| Five-trial pilot | `20261101T152902Z-openflights-444900b0` |
| 25-trial full | `20261101T152915Z-openflights-8fa924ee` |
| MariaDB image/config ID | `sha256:323388181ca5ab00c12c7f7ff63b8210c728d54ef557ce22a552b1d69523a51e` |
| Runner image/config ID | `sha256:78bbacae8b4d65fdf12b79588d3b70a3c9bc5a105165c4b9bbc4aad0e8d849d0` |
| Original exporter ZIP | [ci/openflights-evidence.zip](ci/openflights-evidence.zip) |
| ZIP SHA-256 | `2df17236c7f9ed91acded1525a1eb87ef04f756d40029ac01e1278ecf795c35a` |

The native Ubuntu 24.04 amd64 GitHub-hosted VM reported 4 CPUs, approximately
15.6 GiB Docker RAM, `overlay2`, and about 85.5 GiB physical free space before
building. See [preflight](ci/preflight.json) and [resource observations](ci/preflight-resources.txt).
The database remained limited to 2 CPUs/2 GiB and the worker to 1 CPU/512 MiB.
Physical power, governor and co-tenancy were uncontrolled. The literal power label
in both raw runs identifies these as workflow-validation observations.

## Commands and observed results

The [frozen workflow](https://github.com/majdsl/CU-Databases-Project/blob/2da20124ca1e52128d7cb8c3536736ae139239f7/.github/workflows/correctness.yml)
retains exact commands. Each stage has its original [CI transcript](ci/).

1. `python3 scripts/setup_project.py --project-name "$SESSION_SETUP_PROJECT"`
   passed writable output, 146 lightweight tests and real readback on all five engines.
2. `docker compose -p "$SESSION_SETUP_PROJECT" stop -t 120 db` stopped only the setup DB.
3. `python3 scripts/run_openflights.py --prepare` selected immutable images and
   wrote the format-v2 session and build/package provenance.
4. `--pilot --session "$OPENFLIGHTS_SESSION" --power-condition "$SESSION_POWER"`
   completed five verified trials, each loading all 67,663 routes. Automated CI
   inspection recomputed the raw statistics/summary and checked unchanged controls
   before full. See [pilot inspection](ci/pilot-inspection.txt).
5. `--full` with the same session/power label completed 25 verified trials;
   [full inspection](ci/full-inspection.txt) checked its separate statistics.
   Pilot samples were excluded. Same database startup, selected images and required
   source/runtime/SQL controls were checked across both stages.
6. `--stop --session "$OPENFLIGHTS_SESSION"` recorded the original database exited
   with code 0 and `OOMKilled: false`. Its volume was retained until VM disposal.
7. `python3 scripts/archive_openflights.py --session "$OPENFLIGHTS_SESSION" --output ...`
   exported both raw runs, session, commands, transcripts and build records.
8. Extraction into a different temporary directory followed by standalone `verify.py`
   succeeded for both extracted contents and ZIP, normally and with `-O`.
   The source SHA and tracked status remained unchanged; the job printed
   `OPENFLIGHTS SESSION WORKFLOW PASS`.

The same run also passed optimized lightweight tests (146), offline suites
(102 normally and under `-O`), the live five-engine transaction/restart tutorial,
the mechanism smoke checks and stock tutorials on native amd64/ARM64.
[workflow.json](workflow.json) preserves actual job/step conclusions.

## Inspect or verify without Docker

The [bundle](bundle/) is the original ZIP extracted unchanged for browser inspection.
It includes the [session](bundle/results/20261101T152845Z-openflights-session-ba84d4b7/session.json),
[build manifest](bundle/results/20261101T152845Z-openflights-session-ba84d4b7/build-manifest.json),
[pilot raw result](bundle/results/20261101T152902Z-openflights-444900b0/results.json)
and [full raw result](bundle/results/20261101T152915Z-openflights-8fa924ee/results.json).

From the repository root:

```sh
python3 evidence/reproductions/20261101-ci-openflights-session/verify.py
python3 evidence/reproductions/20261101-ci-openflights-session/bundle/verify.py
python3 -O evidence/reproductions/20261101-ci-openflights-session/bundle/verify.py
python3 evidence/reproductions/20261101-ci-openflights-session/recheck.py
python3 -O evidence/reproductions/20261101-ci-openflights-session/recheck.py
```

After downloading, a separate local extraction passed those byte-integrity checks.
The current exporter's `collect` function also revalidated the extracted session,
raw trials/statistics/summaries, image/control/clean-stop records and reproduced
all 15 original ZIP entries byte-for-byte. This is offline evidence validation,
not a second SQL execution or independent observer attestation.

Privacy review found no credential values, private keys or personal home paths;
no redactions were necessary. Generated credentials and `.env` are excluded.
Public GitHub runner paths are machine paths, not a person's home directory.
The original CI artifact was retrieved through the GitHub connector after the
workspace CLI artifact download returned HTTP 403; no temporary signed download
URL is retained in this archive. Original downloaded bytes were preserved locally.

The exporter ZIP and extracted evidence are committed here because Actions artifacts
expire. Verify the repository's remote copy/checksum when handing this off; a local
ZIP, chat download or an artifact upload alone is not durable backup.

## Limits and separate work

This establishes the complete new-format workflow on the stated hosted Linux
environment. It does not complete Zane's independent physical-laptop reproduction,
establish an OS effect, restore the unavailable assessment-chat ZIP, or prove
byte-identical image reconstruction. Package inventories describe these images;
the separate snapshot-build experiment has its own sources and results.
