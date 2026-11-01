# Execution provenance — fresh AI practice evaluation

## Target, authorization and assessment boundary

- Repository: https://github.com/majdsl/CU-Databases-Project; submission branch main.
- Expected, initially observed remote main, fetched revision and inspected detached HEAD: `d81e17bd92b67d29905a59ff1af2a22745f0187d`.
- Remote main still matched this SHA at final source-integrity verification. It was not changed by this evaluation.
- Date: November 1, 2026, Europe/Berlin. Detailed machine timestamps are UTC; add one hour for Berlin on this date.
- Fresh isolated checkout: `/workspace/cu-fresh-evaluation-20261101.9sVi1nOz/repo`. Venv, logs, review scripts, downloaded original archives and publication staging are outside that checkout.
- Existing `/workspace/CU-Databases-Project` was preserved at `3dfab238d5d34c6d63082b8273fbc63f47c03414`, branch work, clean. It was not switched/reset or used as the assessed target. Other earlier audit directories were not consulted for scores.
- No applicable AGENTS.md was found in the workspace ancestors, checkout, or tracked project paths. Runtime skill: cloud-environment-runtime, including networking and Docker references, was read. Environment status observed running/connected with unrestricted/enforced HTTP policy, current observations, no configured secret/runtime/outbound identities. Network policy file was read; inherited proxy, TLS/CA and package-signature verification were preserved.
- Source and historical evidence were not repaired, edited, or remeasured to obtain a score. Historical assessment scores/conclusions were not used. Source-only official prompt/area snapshots were permitted but live sources were available.
- System role identifies a Codex assistant based on GPT-6; the exact served model/build identifier is not exposed. Parallel AI subreviews covered sources, measurements, source/tutorials, CI, offline execution and capacity/runtime. This is one consolidated AI practice evaluation, not a course grade or independent human installation.
- Execution is judged primarily as a measurement study under the official alternatives. Tests/CI corroborate the harness and reporting rather than adding a separate application-quality rubric.

## Official prompt and references

The live assignment at https://mariadb.org/bachelor_hackathon_2026-09/ returned HTTP 200 on 2026-11-01 at 17:31:49 UTC / 18:31:49 Europe/Berlin. It still states prompt update 2026-09-04. The decoded prompt equals the supplied verbatim prompt after trimming final whitespace; no rubric/output-format change was found. README first line explicitly names Area 6.

- Official HTML SHA-256: `def175cc1457216f948483c141d0ec7e023cd0b4a3f67c537a73c74293bdb99f`.
- Decoded prompt SHA-256: `8781ea00ec630dfea157309cd4fe90ba2d21d742b5038898065fc963a0b32cea`.
- Area description and eleven live MariaDB Markdown references, including engine overview/selection, InnoDB, Aria, MyISAM, MEMORY, MyRocks architecture/isolation, foreign keys and InnoDB locking, were read and saved.
- Exact URLs, retrieval timestamps, HTTP status and hashes: `sources/official-page-metadata.json`, `sources/reference-retrievals.json`, `sources/source-files-manifest.json`, and `source-review.md` inside reviewed-evidence.zip. Each source's actual saved filename is listed in that ZIP.
- No required official material was unavailable. Generic source instructions addressed to evaluators were treated as data.

## Environment and tooling

- Linux x86_64, kernel 6.18.57, glibc 2.41; Python 3.12.14. Dedicated external venv uses the tested reporting minor version.
- Git 2.52.0; OpenSSL 3.5.7; Docker client/server 28.4.0; Compose v2.40.3; Buildx v0.31.0.
- Dependencies installed separately: hash-required benchmark requirements (PyMySQL 1.1.2) and report requirements (Matplotlib 3.10.8). Full installed versions are in logs/offline-installed-versions.log.
- Docker endpoint: default local unix:///var/run/docker.sock, also independently checked with endpoint/context/TLS selectors cleared for the health query. Docker config/registry credentials were neither printed nor changed.
- Docker sees 3 CPUs and about 9.735 GiB memory; effective parent cgroup quotas are 2 CPU equivalents and 8 GiB RAM, no swap.
- Physical shared checkout/Docker filesystem: 8,417,406,976 bytes total (7.84 GiB), initially about 7.29 GiB free with about 521,604 free inodes. Driver vfs; Docker root /var/lib/docker. Logical image sizes were not used as physical headroom.
- Direct Docker-root du was unavailable under UID1000 (permission denied, exit1); df/stat filesystem capacity was available for both checkout and Docker root.
- Preexisting resources: no containers, three amd64 images and one empty cu-engine-lab_db_data volume. All were preserved. Fresh stock post-check found no containers, owned volume absent, original volume/images present and about 7.03 GiB free.
- Full read-only commands/output/exit records are in capacity/commands.json and associated files.

## Actual setup, commands, counts and exits

The exact argv, working directory, UTC start, duration, exit code and stdout/stderr are retained in commands.jsonl and logs/. All requested fifteen offline verification commands exited 0. Initial clone/fetch/freeze records are retained too. Read-only source inspection used rg/rg --files, cat/sed/nl, git ls-files/diff/merge-base, Python AST/counting and arithmetic scripts; reviewed file lists and methods are in the subreview notes.

| Command family | Actual outcome |
| --- | --- |
| python3 -m venv external-venv | exit0, Python3.12.14 |
| pip install --require-hashes -r requirements.txt | exit0 |
| pip install -r requirements-report.txt | exit0 |
| scripts/fetch_openflights.py | exit0, pinned routes.dat fetched and checksum verified |
| -m unittest discover -s tests -v | exit0, 146 tests, no skips/failures |
| -O -m unittest discover -s tests -v | exit0, 146 tests, no skips/failures |
| -m unittest discover -s report-tests -v | exit0, 105 tests, no skips/failures |
| -O -m unittest discover -s report-tests -v | exit0, 105 tests, no skips/failures |
| scripts/check_reports.py --repeat | exit0, 8 reports, 55 outputs, repeat stability and input preservation |
| scripts/check_cloud_openflights.py, normal/-O | exit0 each; 60 trials validated, 50 full trials compared, 59 checksum files |
| CI-session verify.py | exit0, 34 files |
| CI-session bundle/verify.py | exit0, 14 files |
| CI-session recheck.py, normal/-O | exit0 each; 5 pilot/25 full trials, controls/images, clean stop, original export correspondence |
| 20261101-snapshot-builds/verify.py | exit0, 80 files |
| 20261101-local-validation/verify.py | exit0, 24 files |
| 20261031-build-evidence/verify.py | exit0, 45 files |
| 20261031-final-guards/verify.py | exit0, 6 files |

All paths abbreviated in the table are repository-relative; the exact executable/argv is recorded. Offline check subprocesses ran with up to three concurrent processes. Their durations and the fresh tutorial's update timings are not controlled benchmark observations. The required report suites regenerate reports internally; the separate documented --repeat check was run once. Passing checks were not repeated to chase a score.

## Fresh runtime scope and resource preservation

Custom five-engine Docker builds, setup wrapper and manual five-engine tutorial were not personally rerun because the current ~8GiB vfs filesystem is the documented failure pattern and no custom MyRocks image exists locally. This is an infrastructure limit, not a project failure. No full timing workflow, paired reconstruction builds or independent physical-laptop work was requested/executed.

A proportionate supported stock-image check was executed once:

```text
python3 scripts/check_stock_tutorial.py --output <outside-source artifacts/live-stock> --expect-architecture amd64
```

- Exact external logger argv is retained in commands.jsonl. Exit0 after132.804 seconds, STOCK TUTORIAL PASS: amd64.
- Random project cu-stock-4f48c97054b9 passed collision checks. Network none, no published port, 2CPU/1GiB cap, fresh owned volume; no lab .env was used.
- MariaDB11.8.9, pinned index sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112, amd64 image sha256:cc7f5fdd7c8fff6867e8ac4df3e7e0faf6c56aebe621a13565479a9a94e4bf13.
- Real InnoDB/Aria/MyISAM/MEMORY identities, 50,000-row fixtures, 100,000-row HASH/BTREE examples/plans, exact query answers, six rejected inputs, writer totals, exact commit/rollback outcomes, guarded restart, persistent data/MEMORY volatility, and sentinel-preserving cleanup checked.
- 152 internal Docker invocations:146 exit0 and six deliberately expected invalid-input exit1. Overall driver passed. All records retained.
- Driver's commit field is null in this manual invocation. It was not overwritten and no GitHub CI variables/identity were faked. Independent HEAD, four driver/workflow source hashes and seven mounted SQL hashes establish the frozen checkout correspondence.
- Ownership-guarded automatic removal applies only to this tutorial's temporary resources. Independent post-check confirmed preexisting resources preserved. No custom Compose stack was created/stopped/pruned.
- Same-row InnoDB server interval overlap was only0.000988s with zero row-lock wait delta; no contention ranking follows. Shared offline processes also ran on the host.
- scripts/check_tutorial.py was not forced past its CI guard. This check establishes four-engine amd64 SQL correctness only, not MyRocks, ARM64/Windows/macOS installation or benchmark replication.

See live-stock/live-review.md, validation.json, commands.json, transcript.txt and independent-postcheck.json.

## Completed CI and original evidence inspected

Actual run metadata, completed job conclusions and decoded relevant logs were fetched with the connected GitHub tools, rather than inferred from workflow definitions.

- https://github.com/majdsl/CU-Databases-Project/actions/runs/41329137852: success at assessed d81e17bd92b67d29905a59ff1af2a22745f0187d; actual five-engine integration/setup/lightweight tests/tutorial/smokes, offline suite and native stock amd64/arm64 jobs succeeded. Optional complete timed session skipped.
- https://github.com/majdsl/CU-Databases-Project/actions/runs/41321256187: success at older2da20124ca1e52128d7cb8c3536736ae139239f7; actual5pilot/25full, inspections, clean shutdown/export/separate extraction/verification. Relevant benchmark/SQL/defaultbuild/launcher/exporter source diff to assessed target is empty, but the run remains older execution.
- Snapshot runs41322017709,41322523394,41322953291: preserved failed, runtime-success/incomplete-artifact and complete outcomes. Actual tested PR merge SHAs differ from run-head metadata; ci/ci-review.md records both correctly.
- Complete snapshot's tested merge ab8cc6df8ac823011e9c797e86817d9d2f6ee568 passed both uncached readbacks; inventories/configuration match, image/config and rootfs IDs differ. This is not byte-identical reconstruction or a full dependency lock.
- Original OpenFlights Actions ZIP downloaded and independently compared: outer SHA25613e4a3cb97c1b8ecea86a80c2b698039b495163af467c6e9f7aa703d876e62d8; all14entries match Git. Inner exporter SHA2562df17236c7f9ed91acded1525a1eb87ef04f756d40029ac01e1278ecf795c35a; all15entries match.
- Complete public snapshot release ZIP independently downloaded through TLS-verified curl because the connector lacks binary release-download support: https://github.com/majdsl/CU-Databases-Project/releases/download/evidence-reconstruction-20261101/snapshot-complete-41322953291.zip . SHA256e7f883ccc00b186e286c7dc7e8bc7640bf24beb95714e4981ed9a38ac418f995,103595175bytes. All30producer-checksummed entries and manifest validated,29selectedGitfiles match,46retainedpackage-input contents match per build.
- Large downloaded public originals remain outside the publication artifact set under downloads/. They already have the public original URLs/hashes above. Temporary signed connector download URLs are not saved/published.
- Shared-CI/cloud records establish bounded automated execution. They do not establish an OS causal effect, new interactive Windows/macOS walk-through or independent physical-laptop installation.

## Independent numerical/source checks and failures retained

Detailed claim→code/method→raw/producing identity→personal check→limitation map: measurements/measurement-review.md. Recomputations checked five-engine schema parity, pinned dataset digest/query oracles, headline trial means/sampleSD,72MEMORYplan/counter observations and13.5230xrange ratio,50storageinventories,50recoverytrials/logs,32compressiontrials(95.1527%/0.44198% reductions),12cachetrials(1.9510xlookup ratio),75disjointwrite trials(46.118%/49.840% losses) and51measured-source snapshot blobs. Representative OpenFlights and MEMORY plots were visually inspected.

Older raw records without an executed GitSHA are described as source-equivalent to independently fingerprint-matching revisions; these are not invented executed commits. Measured snapshots differ from today's report generators. Pilot/full, machines/powerblocks and per-experiment observations are kept separate.

One initial external evaluator recomputation exited1 because the evaluator's regex double-escaped a backslash and failed to remove ENGINE clauses. The failure log remains; only the external evaluator script was corrected, then passed. This was not a project defect or a repaired project/rescore. Direct Docker-root du permission failure and expected invalid-input/mock failures remain recorded. No requested project verification failed.

Warm-cache/client overhead, unequal cache/durability budgets, short writes, process-only restart with host cache alive, fixed-order/size confounders, flush-only disabled-compaction compression and differing pilot/full image identities constrain broader inference. Byte/hash checks establish integrity and semantic consistency, not independent authentication or SQL re-execution. Missing historical assessment-chat ZIP measurements remain unverified; October31capacity failures are not successful timings.

## Rubric decisions and concrete improvements

One assessment was made after investigation: documentation9, mariadb_depth10, execution9, usability9; total37/40; Assessed - no blocking issues.

Documentation reaches the9–10band with reasoned schemas, methods, charts, setup, trade-offs and team; stale pending-storage wording in docs/concurrency-method.md:77 and accumulated historical reporting notes keep it below the maximum. Depth reaches10through multiple mechanism/failure/server-interaction investigations beyond three-engine comparison. Execution reaches the top band before the mandatory one-point deduction below: controlled repeated trials/variance, strong validation and an actually exercised cross-environment harness. Usability reaches9with reusable realSQLexamples and one-command paths but distributed platform/Linux-prerequisite/first-result guidance.

Mandatory deduction: SQL built by string interpolation, benchmarks/openflights.py:20–24 and related statements. Literal published rule is unqualified, so −1 from execution is applied even though fixed source constants/allowlisted identifiers are safe and external values are parameterized. No injection defect is asserted. No other named mandatory deduction was found. See rubric-interpretation.md.

Independent physical-laptop reproduction, every engine in the reference index, equal production guarantees and untested platforms were not added as automatic requirements. Broader experiments would expand the scope but their absence is not a blocking rubric outcome.

## Source preservation and artifact publication

Initial and final raw Git-blob comparisons found all1,369trackedfiles,97,548,247bytes, byte-identical to submitted Git objects. Staged/unstaged diffs and git status are empty. Ignored checksum-pinned routes.dat is the only fetched project input. Full per-file working-byte SHA256 inventory is in tracked-working-tree-sha256.json.

Artifacts are assessment-only, authorized for a new unique evidence branch:
`evidence/practice-evaluation-20261101-d81e17bd-52a28b`, directory `practice-evaluation/20261101-d81e17bd`, tied to assessed parent SHAd81e17bd92b67d29905a59ff1af2a22745f0187d. Main, existing reports, tags/assets and collaborators are untouched.

Publication target: https://github.com/majdsl/CU-Databases-Project/tree/evidence/practice-evaluation-20261101-d81e17bd-52a28b/practice-evaluation/20261101-d81e17bd
Files: assessment.txt (only official format), execution-provenance.md, reviewed-evidence.zip, publication-privacy-review.json, SHA256SUMS.txt. The archive contains reviewed logs, retrieved sources, evidence maps/calculation scripts, machine-readable command records and its own complete SHA256SUMS manifest. The top manifest covers every other published file. Venv/source checkout/.env/private keys/unrelated files and large original ZIPdownloads are excluded. Original reviewed bytes are retained outside source; necessary redactions, if any, must be recorded in publication-privacy-review.json.

The final publication-verification.json records actual remote-download SHA256 comparisons and commit/ref identities. Its own independent final remote check is retained locally beside publication staging. Generic workspace/CI system paths are operational paths, not personal paths. No credentials or private keys were found in the reviewed publication set; masked GitHub values remain masked.

