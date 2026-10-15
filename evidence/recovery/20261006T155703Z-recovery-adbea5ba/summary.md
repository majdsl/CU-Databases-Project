# Recovery pilot

Run: 20261006T155703Z-recovery-adbea5ba

1000 acknowledged single-row autocommit inserts per trial; 1 round(s).
Each trial uses a fresh volume. No write is in flight at the planned stop.
SIGKILL tests a database-process crash with host/kernel still running, not power loss.

| Engine | Round | Stop | Observation | Intact rows | Missing | Changed | Restart through verification (s) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| InnoDB | 1 | clean | readable | 1000 | 0 | 0 | 4.453 |
| InnoDB | 1 | sigkill | readable | 1000 | 0 | 0 | 2.719 |
| ROCKSDB | 1 | sigkill | readable | 1000 | 0 | 0 | 3.219 |
| ROCKSDB | 1 | clean | readable | 1000 | 0 | 0 | 3.047 |
| MEMORY | 1 | clean | readable | 0 | 1000 | 0 | 1.969 |
| MEMORY | 1 | sigkill | readable | 0 | 1000 | 0 | 3.782 |
| Aria | 1 | sigkill | readable | 1000 | 0 | 0 | 2.266 |
| Aria | 1 | clean | readable | 1000 | 0 | 0 | 2.218 |
| MyISAM | 1 | clean | readable | 1000 | 0 | 0 | 3.000 |
| MyISAM | 1 | sigkill | readable | 1000 | 0 | 0 | 2.484 |

Timing includes Docker startup, observer-container launch, connection polling, full data read and CHECK TABLE.
It is not engine-only recovery latency. Unavailable/unreadable tables have unknown survival, not zero rows.
MEMORY rows are volatile even for clean restarts. Data survival in this test is not a durability guarantee.
The writer holds its connection open until the stop; receipt transfer and host orchestration introduce delay.
Automatic engine recovery may occur; the harness never issues REPAIR TABLE or forces compaction.
Completed means the protocol finished, not that every engine preserved every row.
Raw receipts, observations, source hashes, settings, timings and server logs are saved beside this report.
Retained projects needing review: 0
See docs/recovery-method.md for protocol and limitations.
