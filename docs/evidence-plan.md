# Evidence plan (not completed results)

| Criterion | Required project evidence | Current status |
| --- | --- | --- |
| Documentation | Setup, reasoned benchmark schema and diagram, dataset provenance, methods, charts, recommendations, team | Initial setup documented; remainder pending |
| MariaDB depth | Four engines, actual-engine checks, limits, crash recovery, transaction and locking behaviour | Four-engine setup check implemented; experimental work pending |
| Execution | Equivalent workloads, controlled cache/durability/index settings, repeated runs, raw data, variation, correctness checks | Setup integration check implemented; live validation pending |
| Usability | Short reproducible setup, quick and full runs, worked example, useful interpretation | Initial setup commands; benchmark tutorial pending |

## Experiments to design before implementation

Load time, disk footprint (separate from RAM consumption), point lookups, full scans,
concurrent writes, and crash recovery. Separate common-workload comparisons from
engine-specific capabilities. Treat unsupported features and MEMORY volatility explicitly.
Do not imply that equal SQL means equal durability or transactional guarantees.
Add limits and server-interaction experiments beyond the baseline topic requirements.

Preserve seeds, exact versions, image digests, machine/VM/container settings, row counts,
index definitions, cache conditions, run order and repeated measurements.
Validate data before trusting timing. Report variation, not just best runs.
Use CI for correctness and a controlled machine for performance.
Re-read the published evaluation prompt before submission and audit actual files on main.
