"""Storage helpers for a disposable, isolated MariaDB instance.

The host orchestrator alone stops the server and controls volume lifecycle.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import stat

from .core import Config, ENGINES, dataset_digest, generate_rows
from .run import INSERT, LOCK_NAME, ROOT, runtime_metadata, source_fingerprint, variables, verify_rows


def file_snapshot(root):
    """Metadata only; never follow symlinks or read database file contents."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError("Snapshot directory is missing")
    files, skipped, seen = [], [], set()
    def onerror(error):
        raise error
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=onerror):
        for name in sorted(dirs + names):
            path = Path(directory) / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                skipped.append(relative)
                continue
            if not hasattr(info, "st_blocks"):
                raise RuntimeError("Linux filesystem allocated-block counters required")
            identity = (info.st_dev, info.st_ino)
            files.append({"path": relative, "apparent_bytes": info.st_size,
                          "allocated_bytes": info.st_blocks * 512,
                          "counted": identity not in seen})
            seen.add(identity)
    files.sort(key=lambda entry: entry["path"])
    return {"files": files, "skipped_nonregular_paths": sorted(skipped),
            "regular_file_apparent_bytes": sum(f["apparent_bytes"] for f in files if f["counted"]),
            "regular_file_allocated_bytes": sum(f["allocated_bytes"] for f in files if f["counted"]),
            "scope": "regular files only; hardlinks counted once; directories and nonregular files excluded"}


def load(engine, count, seed):
    if engine not in ENGINES:
        raise ValueError("Unknown engine")
    if os.environ.get("STORAGE_EXPERIMENT") != "isolated-v1" or os.environ.get("DB_NAME") != "engine_lab":
        raise ValueError("Use the isolated storage orchestrator")
    config = Config(rows=count, seed=seed)
    rows = generate_rows(config)
    import pymysql
    with pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                         password=os.environ["DB_PASSWORD"], database="engine_lab",
                         charset="utf8mb4", autocommit=True, connect_timeout=10,
                         read_timeout=300, write_timeout=300) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 0)", (LOCK_NAME,))
            if cursor.fetchone()[0] != 1:
                raise RuntimeError("Another experiment owns the database lock")
            cursor.execute("SHOW TABLES")
            if cursor.fetchall():
                raise RuntimeError("Storage experiment requires an empty engine_lab database")
            cursor.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
            cursor.execute("SET SESSION query_cache_type = OFF")
            cursor.execute("SET SESSION max_heap_table_size = 134217728")
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            if "MariaDB" not in version:
                raise RuntimeError("MariaDB required")
            cursor.execute((ROOT / "sql/benchmark" / (engine.lower() + ".sql")).read_text())
            cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
                           "AND TABLE_NAME = 'benchmark_events'")
            if cursor.fetchone()[0].lower() != engine.lower():
                raise RuntimeError("Engine substitution detected")
            cursor.execute("SHOW CREATE TABLE benchmark_events")
            ddl = cursor.fetchone()[1]
            for offset in range(0, len(rows), config.batch_size):
                cursor.executemany(INSERT, rows[offset:offset + config.batch_size])
            digest = verify_rows(cursor, rows)
            if digest != dataset_digest(rows):
                raise RuntimeError("Dataset checksum mismatch")
            cursor.execute("ANALYZE TABLE benchmark_events")
            analyze = cursor.fetchall()
            if any(str(row[2]).lower() == "error" for row in analyze):
                raise RuntimeError("ANALYZE TABLE failed")
            cursor.execute("SHOW TABLE STATUS WHERE Name = 'benchmark_events'")
            status = dict(zip([column[0] for column in cursor.description], cursor.fetchone()))
            result = {"engine": engine, "config": asdict(config), "server_version": version,
                      "verified_dataset_sha256": digest, "verified_rows": len(rows),
                      "actual_ddl": ddl, "analyze_messages": analyze,
                      "live_engine_reported_table_status": status,
                      "global_variables": variables(cursor, "global"),
                      "session_variables": variables(cursor, "session"),
                      "runtime": runtime_metadata(), "source_sha256": source_fingerprint()}
    # Retain the table for the host's stopped-server file inventory.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot")
    loader = sub.add_parser("load")
    loader.add_argument("--engine", required=True, choices=ENGINES)
    loader.add_argument("--rows", type=int, default=10000)
    loader.add_argument("--seed", type=int, default=20260923)
    args = parser.parse_args()
    result = file_snapshot("/storage") if args.command == "snapshot" else load(args.engine, args.rows, args.seed)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
