# Choosing an engine: recommendations from the measured workloads

**For an application that owns persistent, transactional data, start with InnoDB.
For a rebuildable, RAM-resident reference table, consider MEMORY.
Evaluate Aria for non-transactional persistent reads, MyISAM for a narrowly justified
rebuildable loading workload, and MyRocks when storage pressure warrants further testing.**

These are conditional engineering recommendations for the project's MariaDB 11.8.9 setup.
They combine measured observations with documented engine features; they are not a universal
ranking. The experiments did not implement a booking application or test multi-statement
transactions. A recommendation for that application is an inference from its requirements.

## Choose by requirements first

| Requirement / example | Recommended starting point | Evidence and cost |
| --- | --- | --- |
| Booking records or updates that must commit or roll back together; database-enforced references between tables | InnoDB | Documented transactions, row locking and foreign keys [1,2]. All acknowledged rows survived our tested restarts. Its synthetic datadir growth was the largest measured; do not choose solely by loading speed. |
| Route cache rebuilt from a durable source, with acceptable restart repopulation and enough RAM | MEMORY | Lowest observed OpenFlights mean load and scan times. Every recovery trial lost its rows, including clean restarts. Plan and verify the rebuild before serving requests. |
| Persistent reference table with scans and no multi-statement transaction requirement | Evaluate Aria | Lowest observed OpenFlights scan mean among disk-backed engines; recovery logs showed Aria recovery. Its load mean was the highest. Crash-safe table options do not supply application transactions [3]. |
| Rebuildable batch-loaded reference table where loading time dominates | Compare MyISAM with Aria | MyISAM loaded fastest among disk-backed engines here. Its forced-restart trials all logged crashed-table warnings. Accept the recovery/repair burden explicitly; this is not our default for new authoritative data. |
| Persistent data where disk allocation is the main constraint | Evaluate MyRocks (ROCKSDB) | Smallest measured persistent datadir growth, but slowest OpenFlights scan mean. Larger, sustained workloads and compaction must be tested before claiming a production advantage. |

If the application requires foreign keys, the documented MariaDB support here selects InnoDB
from these five engines [2]. If it only requires transactions, MyRocks is also a candidate,
but its documented isolation restrictions must fit the application [6]. Neither feature
decision can be replaced by a millisecond ranking.

## Measured trade-offs

The columns below deliberately retain their different workloads. They must not be combined
into a single score or used to estimate bytes per OpenFlights route.

| Engine | OpenFlights load, s | OpenFlights full scan, ms | Synthetic datadir growth, MiB | Rows after each tested restart |
| --- | ---: | ---: | ---: | --- |
| InnoDB | 1.1840 ± 0.0383 | 11.4745 ± 0.4860 | 9.129 | 1,000 / 1,000 |
| Aria | 2.0078 ± 0.0305 | 9.7694 ± 0.4150 | 3.730 | 1,000 / 1,000 |
| MyISAM | 0.7932 ± 0.0213 | 10.3507 ± 0.3222 | 1.266 | 1,000 / 1,000; warnings after all forced stops |
| MEMORY | 0.6906 ± 0.0410 | 5.7458 ± 0.3325 | 0.121 overhead only | 0 / 1,000 |
| ROCKSDB | 1.2440 ± 0.0182 | 18.8477 ± 0.3985 | 1.168 | 1,000 / 1,000 |

Sources and statistical units:

- [OpenFlights](openflights-findings.md): 67,663 historical route records; five balanced
  rounds per engine. Values are mean ± sample SD of trial means, not confidence intervals.
  Warm reads include driver/network work. Point-lookup means span only 0.234–0.249 ms
  with overlapping observed ranges, so we make no point-lookup winner claim.
- [Storage](storage-findings.md): 10,000 synthetic event rows; five fresh-volume trials
  per engine. Growth includes whole-datadir files, logs and restart effects. Each engine's
  allocated growth repeated exactly at the measured filesystem resolution; this does not
  eliminate uncertainty. MEMORY's separate live data/index allocation was 8.725 MiB,
  not total server RAM and not the RAM cost of the larger OpenFlights dataset.
- [Recovery](recovery-findings.md): 1,000 acknowledged autocommit inserts per trial;
  five clean and five SIGKILL restarts per engine. Stops occurred between statements,
  with the host and filesystem cache still running. This is not a power-loss test.
  Intact MyISAM rows do not cancel the logged warnings or establish transactional safety.

The [10,000-row synthetic baseline](../evidence/baseline/20260923T121610Z-92b1c313/README.md)
established the controlled load/read procedure. The real route snapshot adds realistic
reference-data distributions. Synthetic events remain useful for controlled updates and
failure tests. They describe different entities and schemas; their timings are not pooled.
All pilot runs remain outside full-run statistics.

## Mechanisms and what we actually established

**InnoDB:** documented transactions, row-level locking, and redo/undo logging support its
role for persistent application state [1]. Row locking allows concurrency on different
records, but conflicting writes can still wait [7]. We verified row contents and restart
survival in the stated protocol. We did not test rollback, deadlock handling, foreign-key
enforcement, or interrupted commits. Its larger small-table allocation is observed;
we did not isolate the cost of individual durability features.

**Aria:** its PAGE format and crash-safe option use logging; the option called
`TRANSACTIONAL` does not provide multi-statement transactions [3]. Recorded recovery
messages are consistent with that documented recovery mechanism. They do not prove
every failure case, and the faster scan mean does not establish that its cache design
caused the difference.

**MyISAM:** separate data/index files, table locking and absence of transactions
distinguish its design [4]. Its loading and storage measurements can matter for a
rebuildable table. Recovery warnings and missing transaction guarantees matter more
when that table is the sole authoritative copy. MariaDB itself encourages considering
Aria for new applications [4]; our loading result is a workload-specific reason to
compare them, not to disregard that guidance.

**MEMORY:** RAM storage explains its volatility; the documentation also permits HASH
and BTREE indexes [5]. Our benchmark explicitly uses BTREE, so it is not a test of
MEMORY's default HASH advantage. The warm-read result does not isolate disk avoidance:
the persistent engines were warmed too. Rebuild time, RAM exhaustion and concurrent
cache refresh remain unmeasured.

**MyRocks:** documented LSM organization and compaction motivate evaluating space and
sustained ingestion [8]. Small measured datadir growth is not a compression ratio or
a steady-state result. Our slow scan does not isolate LSM or compaction as its cause.
MyRocks supports READ COMMITTED and REPEATABLE READ, but not SERIALIZABLE or gap locking
as described in MariaDB's isolation documentation [6]. Those are compatibility checks,
not features proved by our autocommit benchmark.

## Why concurrent-write results do not give a simple engine ranking

The [CPU diagnostic](cpu-findings.md) found that changing runner quota from one to two
CPUs increased four-client disjoint-update throughput by 61.4% / 54.7% for MyISAM / MEMORY
in the morning block and 53.4% / 57.1% in the evening block. Recorded local runner
throttling disappeared at two CPUs. Power blocks remain separate.

Four clients still underperformed two for those engines after the change. We did not
measure server lock waits, server CPU or Python scheduling directly, so table locking
is a possible contributor, not an established sole cause. For future concurrency tests,
start with two runner CPUs, record throttling and fixed power conditions, and measure
server contention before attributing scaling to engine architecture.

## Applying the recommendation

For a hypothetical booking service, choose InnoDB for bookings and related authoritative
records, based on required transactions and references. A separate MEMORY route cache
is optional only when it can be rebuilt and checked from durable data. This architecture
is a design inference, not an implemented or benchmarked multi-table system.

For a static route-analysis service, compare Aria's scan result against MyISAM's load
result using the actual refresh frequency and recovery requirements. If the entire
table is disposable and fits RAM, MEMORY is worth testing. For a storage-constrained
service, shortlist MyRocks but measure realistic data volume, update duration,
compaction and required isolation before adopting it.

Further experiments are needed only to support broader claims: transaction failures,
cold reads, joins, larger-than-memory data, sustained writes, device power loss and
independent hosts are outside this evidence. Five repeats on one laptop, unequal
engine cache/durability budgets and reused-server effects remain limits.
[Correctness CI](ci.md) validates builds and basic engine operation; it is not a
performance or durability benchmark.

## Official feature references

Consulted October 10, 2026 (Europe/Berlin). These describe engine capabilities;
the linked project reports above describe what was measured.

1. [InnoDB introduction](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-storage-engine-introduction)
2. [MariaDB foreign keys](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/optimization-and-indexes/foreign-keys)
3. [Aria table options and recovery](https://mariadb.com/docs/server/server-usage/storage-engines/aria/aria-storage-engine)
4. [MyISAM overview](https://mariadb.com/docs/server/server-usage/storage-engines/myisam-storage-engine/myisam-overview)
5. [MEMORY storage engine](https://mariadb.com/docs/server/server-usage/storage-engines/memory-storage-engine)
6. [MyRocks transactional isolation](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/myrocks-transactional-isolation)
7. [InnoDB lock modes](https://mariadb.com/docs/server/server-usage/storage-engines/innodb/innodb-lock-modes)
8. [MyRocks architecture](https://mariadb.com/docs/server/server-usage/storage-engines/myrocks/about-myrocks-for-mariadb)
