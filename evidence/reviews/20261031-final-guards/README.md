# Final supported-builder guard transcripts

This supplements the sealed [build/evidence validation record](../20261031-build-evidence/README.md)
without changing any file in that archive. Its original `build-normal.txt` and
`build-optimized.txt` cover the initial 13-test collector; the final supported plain
Buildx inspection has two additional parser cases.

At source `13961d3`, the final 15 collector tests pass normally and with `-O`.
`final-manifest-launcher-normal.txt` also preserves the combined 38-test result
(15 collector + 23 launcher). The final complete offline suite has 102 methods;
revision-specific CI runs that suite in both Python modes and performs the real
five-engine OpenFlights lifecycle smoke. No timing pilot/full success is inferred
from these guards.

Run `python verify.py` here to check every file's bytes and complete checksum
coverage using only the standard library. It does not independently rerun SQL or
authenticate the observer. The original 45-file archive has its own unchanged
manifest and standalone verifier.
