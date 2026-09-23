"""Run a small controlled baseline against the dedicated engine_lab database."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import time
import uuid

from .core import Config, ENGINES, dataset_digest, engine_schedule, expected_scan, generate_rows, lookup_ids, row_bytes
from .report import markdown

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = "event_id, route_id, departure_epoch, delay_minutes, fare_cents, passengers, payload"
# SQL is fixed or read from reviewed per-engine files. Data is always parameterized.
SELECT_ALL = "SELECT " + COLUMNS + " FROM benchmark_events ORDER BY event_id"
POINT = "SELECT " + COLUMNS + " FROM benchmark_events WHERE event_id = %s"
INSERT = "INSERT INTO benchmark_events (" + COLUMNS + ") VALUES (%s,%s,%s,%s,%s,%s,%s)"
SCAN = "SELECT COUNT(*), SUM(delay_minutes), SUM(fare_cents * passengers) FROM benchmark_events"
LOCK_NAME = "cu_engine_lab_baseline"
VARIABLES = {
    "version", "version_comment", "version_compile_machine", "version_compile_os",
    "innodb_buffer_pool_size", "innodb_flush_log_at_trx_commit", "innodb_file_per_table",
    "aria_pagecache_buffer_size", "aria_used_for_temp_tables", "aria_recover_options",
    "key_buffer_size", "rocksdb_block_cache_size", "rocksdb_flush_log_at_trx_commit",
    "rocksdb_default_cf_options", "rocksdb_supported_compression_types",
    "query_cache_type", "query_cache_size", "max_heap_table_size", "tmp_table_size",
    "sql_mode", "autocommit", "tx_isolation", "binlog_format", "log_bin", "sync_binlog",
}


def save_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_fingerprint():
    paths = [ROOT / "Dockerfile", ROOT / "requirements.txt", ROOT / "compose.yaml"]
    for directory in ("benchmarks", "sql/benchmark", "docker/mariadb"):
        paths += [p for p in (ROOT / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.exists()}


def runtime_metadata():
    metadata = {"python": sys.version, "platform": platform.platform(), "cpu_count_visible": os.cpu_count(),
                "pymysql": importlib.metadata.version("PyMySQL")}
    for name, path in (("cgroup_memory_max", "/sys/fs/cgroup/memory.max"),
                       ("cgroup_cpu_max", "/sys/fs/cgroup/cpu.max")):
        try:
            metadata[name] = Path(path).read_text().strip()
        except OSError:
            metadata[name] = "unavailable"
    return metadata


def variables(cursor, scope):
    # Only two literal statements; never accept scope or variable names from a user.
    cursor.execute("SHOW GLOBAL VARIABLES" if scope == "global" else "SHOW SESSION VARIABLES")
    return {key: value for key, value in cursor.fetchall() if key.lower() in VARIABLES}


def verify_rows(cursor, rows):
    cursor.execute(SELECT_ALL)
    checksum = hashlib.sha256()
    position = 0
    while batch := cursor.fetchmany(1000):
        for actual in batch:
            if position >= len(rows) or tuple(actual) != rows[position]:
                raise RuntimeError("Loaded data differs from the generated dataset")
            checksum.update(row_bytes(actual))
            position += 1
    if position != len(rows):
        raise RuntimeError("Loaded row count differs from the generated dataset")
    return checksum.hexdigest()


def measure(cursor, statement, params, expected):
    start = time.perf_counter_ns()
    cursor.execute(statement, params)
    actual = cursor.fetchone()
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
    if actual is None or tuple(actual) != tuple(expected):
        raise RuntimeError("Query returned an incorrect result")
    return elapsed_ms


def trial(connection, engine, config, rows, round_number):
    with connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES "
                       "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", ("benchmark_events",))
        if cursor.fetchone() is not None:
            raise RuntimeError("benchmark_events already exists; refusing to overwrite it. See troubleshooting.")
        ddl = (ROOT / "sql/benchmark" / (engine.lower() + ".sql")).read_text()
        cursor.execute(ddl)
        try:
            cursor.execute("SELECT ENGINE FROM information_schema.TABLES "
                           "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s", ("benchmark_events",))
            actual_engine = cursor.fetchone()[0]
            if actual_engine.lower() != engine.lower():
                raise RuntimeError("Engine substitution detected")
            cursor.execute("SHOW CREATE TABLE benchmark_events")
            actual_ddl = cursor.fetchone()[1]
            start = time.perf_counter_ns()
            for offset in range(0, len(rows), config.batch_size):
                cursor.executemany(INSERT, rows[offset:offset + config.batch_size])
            load_seconds = (time.perf_counter_ns() - start) / 1_000_000_000
            cursor.execute("ANALYZE TABLE benchmark_events")
            analyze = cursor.fetchall()
            if any(str(row[2]).lower() == "error" for row in analyze):
                raise RuntimeError("ANALYZE TABLE failed: " + str(analyze))
            verified_digest = verify_rows(cursor, rows)
            keys = lookup_ids(config.seed, round_number, len(rows), config.lookups)
            aggregate = expected_scan(rows)
            # Entire dataset was read for validation. This is explicitly a warm-read experiment.
            for key in keys[:min(50, len(keys))]:
                measure(cursor, POINT, (key,), rows[key - 1])
            measure(cursor, SCAN, None, aggregate)
            lookups = [measure(cursor, POINT, (key,), rows[key - 1]) for key in keys]
            scans = [measure(cursor, SCAN, None, aggregate) for _ in range(config.scans)]
            cursor.execute("EXPLAIN " + POINT, (keys[0],))
            point_plan = cursor.fetchall()
            cursor.execute("EXPLAIN " + SCAN)
            scan_plan = cursor.fetchall()
            cursor.execute("SHOW TABLE STATUS WHERE Name = 'benchmark_events'")
            table_status = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
            return {"engine": engine, "round": round_number + 1, "load_seconds": load_seconds,
                    "lookup_ms": lookups, "scan_ms": scans, "lookup_ids": keys,
                    "verified_dataset_sha256": verified_digest, "actual_ddl": actual_ddl,
                    "point_explain": point_plan, "scan_explain": scan_plan,
                    "analyze_messages": analyze,
                    "table_status_engine_reported_not_physical_disk_bytes": table_status}
        finally:
            # Only remove the table successfully created by this trial.
            cursor.execute("DROP TABLE benchmark_events")


def run(config, output):
    config.validate()
    if os.environ.get("DB_NAME") != "engine_lab":
        raise ValueError("Only the dedicated engine_lab database is allowed")
    import pymysql
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    rows = generate_rows(config)
    schedule = engine_schedule(config.seed, config.rounds)
    result = {"format_version": 1, "run_id": run_id, "status": "running", "config": asdict(config),
              "dataset_sha256": dataset_digest(rows), "schedule": schedule, "trials": [],
              "source_sha256": source_fingerprint(), "runtime": runtime_metadata(),
              "cache_condition": "post-load, post-analyze, fully verified and explicitly warmed",
              "limitations": ["single client", "same server reused", "not equal durability guarantees",
                              "not steady-state MyRocks compaction", "no cold-cache claim",
                              "not a physical disk-size measurement", "no concurrency or crash experiments yet"]}
    save_json(directory / "results.json", result)
    try:
        with pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                             password=os.environ["DB_PASSWORD"], database="engine_lab", charset="utf8mb4",
                             autocommit=True, connect_timeout=10, read_timeout=300, write_timeout=300) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0)", (LOCK_NAME,))
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError("Another baseline run holds the database lock")
                cursor.execute("SELECT VERSION()")
                result["server_version"] = cursor.fetchone()[0]
                if "MariaDB" not in result["server_version"]:
                    raise RuntimeError("This experiment requires MariaDB")
                cursor.execute("SHOW ENGINES")
                available = {row[0].lower(): row[1].upper() for row in cursor.fetchall()}
                if any(available.get(engine.lower()) not in ("YES", "DEFAULT") for engine in ENGINES):
                    raise RuntimeError("All five engines must be available")
                cursor.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
                cursor.execute("SET SESSION query_cache_type = OFF")
                cursor.execute("SET SESSION max_heap_table_size = 134217728")
                result["global_variables"] = variables(cursor, "global")
                result["session_variables"] = variables(cursor, "session")
            save_json(directory / "results.json", result)
            for round_number, order in enumerate(schedule):
                for position, engine in enumerate(order):
                    print(f"Round {round_number + 1}/{config.rounds}: {engine}", flush=True)
                    item = trial(connection, engine, config, rows, round_number)
                    if item["verified_dataset_sha256"] != result["dataset_sha256"]:
                        raise RuntimeError("Dataset checksum mismatch")
                    item["position"] = position + 1
                    result["trials"].append(item)
                    save_json(directory / "results.json", result)
            # Connection close releases the advisory lock, including on failure.
        result["status"] = "completed"
        report = markdown(result)
        (directory / "summary.md").write_text(report, encoding="utf-8")
        save_json(directory / "results.json", result)
        print(report)
        print("Saved:", directory)
    except Exception as error:
        result["status"] = "failed"
        result["error_type"] = type(error).__name__
        (directory / "summary.md").unlink(missing_ok=True)
        save_json(directory / "results.json", result)
        print("Partial results saved:", directory, file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--lookups", type=int, default=200)
    parser.add_argument("--scans", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--output", type=Path, default=Path("/results"))
    args = parser.parse_args()
    config = Config(args.rows, args.rounds, args.lookups, args.scans, args.batch_size, args.seed)
    try:
        run(config, args.output)
    except Exception as error:
        print("FAILED:", str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
