# Measured cache-pressure sources

This immutable snapshot preserves the sources behind the October 16 pilot/full
cache-pressure observations. It is not a second runnable checkout or the current
development code. It allows reporting to verify historical source identities after
the live orchestrator and Compose configuration evolve.

All 25 unique files were exported from Git revision
`db0639c0194092e8c338a68f2f9f24ed024d7a5f` of
`https://github.com/majdsl/CU-Databases-Project`. Their host/worker fingerprints were
verified against both original runs, accepting recorded Windows CRLF or repository
LF representations. No archived observation or recorded hash was replaced.

`manifest.json` specifies the exact three host and 23 worker paths, original Git
blob IDs and LF/CRLF SHA-256 values. The report pins the manifest digest, verifies
snapshot contents, and compares the original measurement fingerprints. Editing
both a source and its manifest is rejected rather than silently redefining the
measured experiment. Git metadata and network access are not needed to validate it.

The generated statistics identify the historical snapshot separately from the
current report generator. This does not establish byte-identical pilot/full images
or reconstruct missing historical package/layer metadata. Those documented limits
remain unchanged; new experiments need their own source/image provenance.
