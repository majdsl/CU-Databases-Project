# Local baseline results

Run: 20260923T121610Z-92b1c313

10000 synthetic rows; 5 load/read rounds per engine.
Warm/post-verification reads; single client; client-observed timings.
This is a baseline, not a general ranking or a durability-equivalent comparison.

| Engine | Metric | Unit | Trials | Mean | Sample SD | Min | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| InnoDB | load | s | 5 | 0.3099 | 0.0178 | 0.2888 | 0.3352 |
| InnoDB | point_lookup | ms | 5 | 0.2171 | 0.0131 | 0.2087 | 0.2399 |
| InnoDB | full_scan | ms | 5 | 1.7819 | 0.1011 | 1.6884 | 1.9207 |
| Aria | load | s | 5 | 0.2446 | 0.0105 | 0.2371 | 0.2627 |
| Aria | point_lookup | ms | 5 | 0.2255 | 0.0226 | 0.2107 | 0.2653 |
| Aria | full_scan | ms | 5 | 1.6254 | 0.0796 | 1.5399 | 1.7301 |
| MyISAM | load | s | 5 | 0.0938 | 0.0011 | 0.0925 | 0.0947 |
| MyISAM | point_lookup | ms | 5 | 0.2383 | 0.0532 | 0.2113 | 0.3335 |
| MyISAM | full_scan | ms | 5 | 1.6501 | 0.0995 | 1.5607 | 1.8079 |
| MEMORY | load | s | 5 | 0.0893 | 0.0053 | 0.0842 | 0.0956 |
| MEMORY | point_lookup | ms | 5 | 0.2131 | 0.0181 | 0.2025 | 0.2452 |
| MEMORY | full_scan | ms | 5 | 1.0690 | 0.0425 | 1.0163 | 1.1202 |
| ROCKSDB | load | s | 5 | 0.1761 | 0.0115 | 0.1648 | 0.1936 |
| ROCKSDB | point_lookup | ms | 5 | 0.2201 | 0.0047 | 0.2131 | 0.2251 |
| ROCKSDB | full_scan | ms | 5 | 2.6407 | 0.0536 | 2.5743 | 2.7124 |

SD for reads is across per-round query means; raw individual timings are in results.json.
Trials reuse one server and are not independent machine replications.
Load completion does not establish equal persistence or compaction completion.
See docs/benchmark-method.md for design, settings and limitations.
