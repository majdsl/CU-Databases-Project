# October 31 practice-audit follow-up

The [supplied assessment](../evidence/evaluations/20261031-supplied-audit/README.md)
reports **37/40** for `main` at
`b5c16bd2db3c352539e720b4aafd62b0fb4be50a`: documentation 9, MariaDB depth 10,
execution 9 and usability 9, with no blocking issues. This is a practice review,
not a course grade. These changes address its findings; they do not award a new score.

## Changes made

| Finding | Change | Inspect |
| --- | --- | --- |
| Current guidance contradicts completed work or quotes old counts as current | The storage method links completed pilot/full evidence. CI avoids repeated current totals. Stock-tutorial guidance distinguishes the dated six-file validation from today's seven-file sequence. | [Storage method](storage-method.md), [CI](ci.md), [stock validation](stock-tutorial-validation.md); documentation correction `d17c65c` |
| Image IDs alone cannot explain a future rebuild | New OpenFlights sessions retain effective Dockerfile hashes, declared base/available registry descriptors, selected image config/filesystem identities, installed package inventories and tool/builder observations. A manifest checksum is required for new sessions. | [Build records and limits](build-reconstruction.md), [image provenance](image-provenance.md) |
| The first-time path leaves operational details implicit | The guide explains stopping the owned setup database, fixed session/source state between stages, delayed worker output, raw-result locations and exporting evidence after a clean stop. | [Setup](setup.md), [prepare → pilot → full → stop → save](openflights-reproduction.md) |
| Local measurements can be lost with a workspace or chat | A completed-session exporter checks both raw runs and recorded controls, preserves pilot/full separation, and produces a portable ZIP with hashes and an offline verifier. | [Save a completed run](openflights-reproduction.md#save-a-completed-run), [exporter](../scripts/archive_openflights.py) |

## Evidence boundaries and remaining work

The [October 31 development validation](../evidence/reviews/20261031-build-evidence/README.md)
preserves the successful fresh setup, frozen offline checks, actual build/package
records and two capacity failures. Both pilot attempts stopped before timed trials;
the managed sandbox's disk limit prevented a new full timing run. Every database
volume and all pre-existing evidence were retained. The exporter has fixture-level
full-session validation; a successful real format-v2 pilot/full/export remains a
separate validation task on a host with adequate physical capacity.
The [final guard transcripts](../evidence/reviews/20261031-final-guards/README.md)
supplement the original validation logs; CI also checks both sealed archives'
complete byte coverage.

The supplied assessment's separate chat became unavailable before its raw-results ZIP
was transferred. Its reported October 31 pilot/full identities are preserved in the
assessment record, but their raw files are not present here or confirmed on GitHub.
The assessment text is archived as supplied evidence, not as independent verification
of those runs. A later new run must retain its own identity and cannot replace them.

The October 30 [cloud Linux reproduction](openflights-linux-reproduction.md) remains
separate from the original laptop measurements. Historical raw files, source snapshots
and image identities are preserved. Shared cloud timings do not identify an OS effect
or count as a physical-laptop reproduction.

Installed package versions and available registry metadata improve inspection; they do
not lock transitive repositories, retain all package binaries, attest every build input
or guarantee byte-identical reconstruction. A signed package-snapshot strategy and
paired clean-build study remain separate future work.

Zane's independent physical-laptop reproduction and reader feedback remain pending.
When supplied, preserve his original ZIP, verify its source/conditions/raw results,
compare per-engine full-run means and sample SD without pooling pilots or hosts,
and credit his contribution. Existing stock-image Windows correctness records do
not establish that this independent run is complete.

A study varying only InnoDB buffer-pool capacity is optional. The existing table-size
experiment's confounds remain disclosed; no new cache-causation claim is made here.
