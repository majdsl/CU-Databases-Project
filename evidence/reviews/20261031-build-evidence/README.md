# Build-record and evidence-export validation — October 31, 2026

This is correctness/development evidence. **No new timing pilot or full run completed
in this follow-up.** It does not replace the archived October 30 measurements or
recover the unavailable separate audit's raw ZIP.

## Source and checks

- Initial implementation: `e09685102cc6620b453860fbde4f9ae14e1bb60c`.
- Final collector fix/preparation: `13961d3` (full SHA in `verification.json`).
- 146 lightweight tests passed normally and with `-O`; the fresh container setup also
  passed all 146 tests and verified actual engines/row readback for all five engines.
- All 100 offline tests passed normally and with `-O` on a frozen checkout at
  `e096851`. This included all eight report generators, repeated outputs and archive
  guards. Earlier attempts on the changing development worktree correctly rejected
  changed inputs; both failed logs are retained, followed by the successful frozen logs.
- The final supported-builder parser has 15 tests (normal and `-O`), alongside the
  23 launcher and eight exporter guards. The repository's current complete offline
  suite contains 102 test methods; CI runs the final combined suite in both modes.
- Independent read-only code review found no actionable issue in the manifest or
  exporter. Fixture checks cover secret exclusion, unsupported/ambiguous provenance,
  immutable probes, manifest/source drift, v1/v2 compatibility, raw corruption,
  pilot/full separation, safe paths, no-overwrite races and standalone ZIP verification.

See the [Correctness workflow](https://github.com/majdsl/CU-Databases-Project/actions/workflows/correctness.yml)
for revision-specific Ubuntu five-engine/launcher smoke, normal/optimized offline
checks and native stock tutorial amd64/ARM64 jobs. A workflow definition or pending
run is not itself a passing result.

## Actual build-record collection

The `sessions/` records preserve three distinct preparations, including two failed
pilot attempts. The final two use format version 2 at the corrected collector source.
Package probes completed successfully, without starting MariaDB or creating anonymous
volumes: 165 installed database packages and 87 runner packages; Python 3.12.15,
PyMySQL 1.1.2 and pip 25.0.1. Both declared base indexes resolved unique Linux amd64
platform/config/compressed-layer descriptors. The final collector observed Docker
28.4.0, Compose 2.40.3, Buildx v0.31.0 and the existing Docker builder's BuildKit
v0.24.0 without bootstrap. Manifests retain full selected output/config and filesystem
layer identities and effective Dockerfile/adapter hashes. Installed versions remain
observations, not a package lock or a byte-identical reconstruction guarantee.

The first untimed preparation exposed that Buildx does not support the attempted
inspection `--format` flag. Its manifest explicitly marked the builder unavailable.
The supported plain inspection was implemented/tested before the later preparations;
no measurement uses the earlier collector as if it had captured a builder version.

## Capacity failures and resource preservation

The shared managed host uses Debian userspace and nested Docker's `vfs` driver,
not native Ubuntu or a physical laptop. Its filesystem is about 8 GB. Docker's
logical sizes understated the physical copied-layer headroom required here.

1. Project `cu-openflights-bd4c242ae5784f8a8fa56796c9a5f73c` failed MariaDB
   initialization with ENOSPC. No worker/timing workload ran.
2. After scoped cleanup, a new independent project
   `cu-openflights-7d351fd3a23448cfb99c6e43732cb99f` started MariaDB successfully but
   its worker failed the initial output-directory write probe with ENOSPC, before
   controls or timed trials. It was not retried as a successful pilot.

Both failed sessions, transcripts, inspected container states and logs are retained.
Only newly created disposable stopped containers and exact owned unused image tags
were removed after recording diagnostics. The second failed database was stopped
cleanly first. **Every database volume, including setup and failed attempts, remains.**
No pre-existing container, volume, image or historical evidence was removed; no
managed environment settings or credentials were changed or republished.
`verification.json`, capacity-recovery JSON and the 946-file baseline substantiate
these bounds. The successful setup's container was removed after its clean stop;
its volume and observations were retained.

Fresh Ubuntu CI validates correctness with ordinary Docker storage. A new complete
pilot/full/export on a host with adequate physical capacity is still needed to
validate the full format-v2 archive path with real timings; it must have new run IDs.
Do not fabricate or import aggregate-only observations into a raw-results folder.

## Reproduce the validation

Run the repository's normal/optimized unit and offline suites from a frozen checkout.
For a new real measurement, follow the [session guide](../../../docs/openflights-reproduction.md),
check physical disk headroom, prepare once, inspect the pilot, run full, stop and
export. The external `build/` adapter supplied CA trust through temporary BuildKit
secret mounts and explicit COPY modes for this managed session; runtime settings and
package version requirements were unchanged. Its private certificate contents and
`.env` are excluded. `validation/runtime-preparation.json` records the scoped access
preparation for the new empty results directory; it is not a command to alter an
existing checkout or database.

Run `python verify.py` from this archive directory (use `python3` on Linux) to
check every archived file and complete SHA-256 coverage without Docker or project
dependencies. This verifies bytes, not authenticity or SQL execution.
