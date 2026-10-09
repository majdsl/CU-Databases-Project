# Recovery experiment

Run: 20261006T161514Z-recovery-99656d7e

1000 acknowledged single-row autocommit inserts per trial; 5 round(s).
Each trial uses a fresh volume. No write is in flight at the planned stop.
SIGKILL tests a database-process crash with host/kernel still running, not power loss.

| Engine | Round | Stop | Observation | Intact rows | Missing | Changed | Restart through verification (s) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| InnoDB | 1 | clean | readable | 1000 | 0 | 0 | 2.719 |
| InnoDB | 1 | sigkill | readable | 1000 | 0 | 0 | 2.625 |
| ROCKSDB | 1 | sigkill | readable | 1000 | 0 | 0 | 1.953 |
| ROCKSDB | 1 | clean | readable | 1000 | 0 | 0 | 3.031 |
| MEMORY | 1 | clean | readable | 0 | 1000 | 0 | 2.485 |
| MEMORY | 1 | sigkill | readable | 0 | 1000 | 0 | 2.953 |
| Aria | 1 | sigkill | readable | 1000 | 0 | 0 | 2.953 |
| Aria | 1 | clean | readable | 1000 | 0 | 0 | 3.015 |
| MyISAM | 1 | clean | readable | 1000 | 0 | 0 | 2.469 |
| MyISAM | 1 | sigkill | readable | 1000 | 0 | 0 | 2.234 |
| ROCKSDB | 2 | sigkill | readable | 1000 | 0 | 0 | 2.250 |
| ROCKSDB | 2 | clean | readable | 1000 | 0 | 0 | 1.953 |
| MEMORY | 2 | clean | readable | 0 | 1000 | 0 | 2.718 |
| MEMORY | 2 | sigkill | readable | 0 | 1000 | 0 | 5.531 |
| Aria | 2 | sigkill | readable | 1000 | 0 | 0 | 3.594 |
| Aria | 2 | clean | readable | 1000 | 0 | 0 | 3.453 |
| MyISAM | 2 | clean | readable | 1000 | 0 | 0 | 2.187 |
| MyISAM | 2 | sigkill | readable | 1000 | 0 | 0 | 2.516 |
| InnoDB | 2 | sigkill | readable | 1000 | 0 | 0 | 2.672 |
| InnoDB | 2 | clean | readable | 1000 | 0 | 0 | 1.953 |
| MEMORY | 3 | clean | readable | 0 | 1000 | 0 | 2.218 |
| MEMORY | 3 | sigkill | readable | 0 | 1000 | 0 | 2.062 |
| Aria | 3 | sigkill | readable | 1000 | 0 | 0 | 2.437 |
| Aria | 3 | clean | readable | 1000 | 0 | 0 | 2.187 |
| MyISAM | 3 | clean | readable | 1000 | 0 | 0 | 2.454 |
| MyISAM | 3 | sigkill | readable | 1000 | 0 | 0 | 1.922 |
| InnoDB | 3 | sigkill | readable | 1000 | 0 | 0 | 2.312 |
| InnoDB | 3 | clean | readable | 1000 | 0 | 0 | 2.656 |
| ROCKSDB | 3 | clean | readable | 1000 | 0 | 0 | 3.500 |
| ROCKSDB | 3 | sigkill | readable | 1000 | 0 | 0 | 3.172 |
| Aria | 4 | sigkill | readable | 1000 | 0 | 0 | 2.203 |
| Aria | 4 | clean | readable | 1000 | 0 | 0 | 2.172 |
| MyISAM | 4 | clean | readable | 1000 | 0 | 0 | 3.515 |
| MyISAM | 4 | sigkill | readable | 1000 | 0 | 0 | 1.968 |
| InnoDB | 4 | sigkill | readable | 1000 | 0 | 0 | 2.250 |
| InnoDB | 4 | clean | readable | 1000 | 0 | 0 | 2.187 |
| ROCKSDB | 4 | clean | readable | 1000 | 0 | 0 | 2.969 |
| ROCKSDB | 4 | sigkill | readable | 1000 | 0 | 0 | 2.704 |
| MEMORY | 4 | sigkill | readable | 0 | 1000 | 0 | 3.359 |
| MEMORY | 4 | clean | readable | 0 | 1000 | 0 | 3.000 |
| MyISAM | 5 | clean | readable | 1000 | 0 | 0 | 1.922 |
| MyISAM | 5 | sigkill | readable | 1000 | 0 | 0 | 3.485 |
| InnoDB | 5 | sigkill | readable | 1000 | 0 | 0 | 2.969 |
| InnoDB | 5 | clean | readable | 1000 | 0 | 0 | 2.140 |
| ROCKSDB | 5 | clean | readable | 1000 | 0 | 0 | 2.172 |
| ROCKSDB | 5 | sigkill | readable | 1000 | 0 | 0 | 2.719 |
| MEMORY | 5 | sigkill | readable | 0 | 1000 | 0 | 1.968 |
| MEMORY | 5 | clean | readable | 0 | 1000 | 0 | 2.047 |
| Aria | 5 | clean | readable | 1000 | 0 | 0 | 2.234 |
| Aria | 5 | sigkill | readable | 1000 | 0 | 0 | 2.766 |

Timing includes Docker startup, observer-container launch, connection polling, full data read and CHECK TABLE.
It is not engine-only recovery latency. Unavailable/unreadable tables have unknown survival, not zero rows.
MEMORY rows are volatile even for clean restarts. Data survival in this test is not a durability guarantee.
The writer holds its connection open until the stop; receipt transfer and host orchestration introduce delay.
Automatic engine recovery may occur; the harness never issues REPAIR TABLE or forces compaction.
Completed means the protocol finished, not that every engine preserved every row.
Raw receipts, observations, source hashes, settings, timings and server logs are saved beside this report.
Retained projects needing review: 0
See docs/recovery-method.md for protocol and limitations.
