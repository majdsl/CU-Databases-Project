# Execution and usability validation — October 30, 2026

Development checks based on main `62ca1fa128ba1c41b9905cf06ec1c0fa8a167ace` with
working changes. `validation.json` pins the checked source bytes and records the
actual image identities and test scope. These are correctness/control checks, not
new performance measurements or an evaluator score.

- 146 lightweight tests passed normally and with optimized Python.
- The full offline suite passed 74 tests in each mode, regenerating all eight reports
  twice and preserving input bytes. Three additional result-readback cases then
  joined the launcher guards; all 21 launcher cases passed in both modes. The final
  offline suite discovers 77 tests, which CI executes on the published source tree.
- The portable sealed-cloud checker validates laptop/cloud results, comparisons,
  measured source and 59 archive file checksums; corruption and Windows-path guards
  reject bad inputs. The historical archive validator is unchanged.
- A real five-engine OpenFlights correctness smoke deliberately retargeted the
  session's unique runner build tag to the DB image. Actual worker inspection still
  matched the selected immutable runner ID before and after execution. SQL and
  source/runtime/SQL controls passed; the DB stopped cleanly and its volume remains.
- A disposable 0755 host-owned directory rejected runner UID 10001. A scoped named-user
  ACL allowed output without changing directory ownership or an existing file's
  contents/owner/mode. The setup wrapper prints the repair but never applies it.
- All 941 pre-existing evidence/provenance files and both original database volume
  metadata records were preserved. No environment settings were changed.

The managed executor uses Debian 13 userspace, Linux amd64 and nested Docker/vfs.
The build-only external adapter supplied the cloud CA and readable COPY permissions;
repository Dockerfiles remained unchanged. Existing cached layers were reused.
New session volumes are retained. The record excludes passwords and private config.

See the [launcher guide](../../../docs/openflights-reproduction.md),
[setup prerequisite](../../../docs/setup.md#native-linux-output-prerequisite), and
[CI scope](../../../docs/ci.md). Zane's physical-laptop reproduction remains separate.
