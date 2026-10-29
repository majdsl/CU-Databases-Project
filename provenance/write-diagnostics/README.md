# Measured write-diagnostics sources

This is an immutable source snapshot for the October 17 pilot/full measurements,
not a second runnable checkout and not the current application source. It lets
offline reporting verify the actual measured sources even after unrelated source
files change. Raw measurements and their recorded fingerprints are unchanged.

The 26 files were exported from Git revision
`c000a91c410dba7e19f6e00be01da1e1b7b55300` of
`https://github.com/majdsl/CU-Databases-Project`. Every exported file was checked
against the original host/worker SHA-256 fingerprints in both archived runs,
accepting the measured Windows CRLF or repository LF representation. The old
Dockerfile intentionally lacks the later compression-orchestrator `COPY` line.

`manifest.json` records the exact host/worker path sets, Git blob IDs, and
LF/CRLF SHA-256 values. The report checks both the snapshot and the unchanged
measurement fingerprints, and pins the manifest digest; it does not trust a modified snapshot just because
the manifest was edited to match. No Git history or network is needed to report
from a downloaded source archive.

Current report-generator provenance is recorded separately in the generated
statistics JSON, alongside the snapshot revision/manifest digest. That metadata
does not imply the current source or newly built images produced the old timings.
Changing the snapshot is not a way to accommodate new application development:
new measurements need their own source provenance.
