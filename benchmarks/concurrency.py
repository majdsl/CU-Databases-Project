"""Fixed-total-work write scaling; correctness checked outside the timed interval."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import threading
import time
import uuid

from .core import Config, ENGINES, dataset_digest, describe, engine_schedule, generate_rows
from .run import INSERT, LOCK_NAME, ROOT, runtime_metadata, save_json, source_fingerprint, variables, verify_rows

UPDATE = "UPDATE benchmark_events SET fare_cents = fare_cents + 1 WHERE event_id = %s"
CLIENTS = (1, 2, 4)
MODES = ("disjoint", "hotspot")


def streams(rows, total, clients, mode):
    if clients not in CLIENTS or mode not in MODES or rows < clients:
        raise ValueError("Invalid concurrency workload")
    if not 100 <= total <= 100000 or total % 4:
        raise ValueError("updates must be 100..100000 and divisible by four")
    # Same total statement count at every client count. Each disjoint client owns a partition.
    return [[(worker + 1 + (i % ((rows - worker - 1) // clients + 1)) * clients)
             if mode == "disjoint" else 1 + (i * clients + worker) % min(16, rows)
             for i in range(total // clients)] for worker in range(clients)]


def expected_rows(rows, keys):
    increments = Counter(key for stream in keys for key in stream)
    return [tuple(list(row[:4]) + [row[4] + increments[row[0]]] + list(row[5:])) for row in rows]


def connect():
    import pymysql
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
                           password=os.environ["DB_PASSWORD"], database="engine_lab", charset="utf8mb4",
                           autocommit=True, connect_timeout=10, read_timeout=60, write_timeout=60)


def configure(cursor):
    cursor.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
    cursor.execute("SET SESSION query_cache_type = OFF")
    cursor.execute("SET SESSION max_heap_table_size = 134217728")
    cursor.execute("SET SESSION lock_wait_timeout = 30")
    cursor.execute("SET SESSION innodb_lock_wait_timeout = 30")


def write_worker(keys, barrier, connection_factory=connect):
    timings = []
    try:
        with connection_factory() as connection:
            with connection.cursor() as cursor:
                configure(cursor)
                barrier.wait(timeout=30)
                for key in keys:
                    start = time.perf_counter_ns()
                    cursor.execute(UPDATE, (key,))
                    elapsed = (time.perf_counter_ns() - start) / 1e6
                    if cursor.rowcount != 1:
                        raise RuntimeError("Update did not affect exactly one row")
                    timings.append(elapsed)
                finished = time.perf_counter_ns()
        return {"completed": len(timings), "latency_ms": timings, "finished_ns": finished}
    except Exception as error:
        barrier.abort()
        # Do not retry: a disconnect can make the commit outcome uncertain.
        return {"completed": len(timings), "latency_ms": timings,
                "error_type": type(error).__name__,
                "error_code": error.args[0] if error.args and type(error.args[0]) is int else None}


def execute_workers(keys, connection_factory=connect):
    clock = {}
    barrier = threading.Barrier(len(keys), action=lambda: clock.update(start=time.perf_counter_ns()))
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        futures = [pool.submit(write_worker, stream, barrier, connection_factory) for stream in keys]
        workers = [future.result() for future in futures]
    result = {"workers": workers, "completed": sum(w["completed"] for w in workers)}
    if any("error_type" in w for w in workers):
        result["status"] = "failed"
    else:
        elapsed = (max(w["finished_ns"] for w in workers) - clock["start"]) / 1e9
        if elapsed <= 0:
            raise RuntimeError("Invalid elapsed time")
        result.update(status="completed", elapsed_seconds=elapsed,
                      updates_per_second=result["completed"] / elapsed)
    # Monotonic timestamps are only useful for computing this interval.
    for worker in workers:
        worker.pop("finished_ns", None)
    return result


def trial(connection, engine, config, rows, clients, mode, total):
    keys = streams(len(rows), total, clients, mode)
    with connection.cursor() as cursor:
        cursor.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
                       "AND TABLE_NAME = %s", ("benchmark_events",))
        if cursor.fetchone() is not None:
            raise RuntimeError("Existing benchmark_events table: refusing to overwrite")
        cursor.execute((ROOT / "sql/benchmark" / (engine.lower() + ".sql")).read_text())
        try:
            cursor.execute("SHOW CREATE TABLE benchmark_events")
            ddl = cursor.fetchone()[1]
            cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
                           "AND TABLE_NAME = %s", ("benchmark_events",))
            if cursor.fetchone()[0].lower() != engine.lower():
                raise RuntimeError("Engine substitution detected")
            for offset in range(0, len(rows), config.batch_size):
                cursor.executemany(INSERT, rows[offset:offset + config.batch_size])
            before = verify_rows(cursor, rows)
            result = execute_workers(keys)
            result.update(engine=engine, clients=clients, mode=mode, actual_ddl=ddl,
                          initial_dataset_sha256=before, attempted_updates=total)
            if result["status"] == "completed":
                expected = expected_rows(rows, keys)
                result["verified_final_sha256"] = verify_rows(cursor, expected)
                if result["completed"] != total:
                    raise RuntimeError("Incomplete write count")
            return result
        finally:
            cursor.execute("DROP TABLE benchmark_events")


def report(result):
    if result["status"] != "completed":
        raise ValueError("Cannot summarize an incomplete run")
    lines = ["# Concurrent update results", "", "Run: " + result["run_id"], "",
             "Fixed total updates per trial; autocommit; warm data; no automatic retries.",
             "Throughput includes worker scheduling and server/client overhead. Durability is not equivalent.", "",
             "| Engine | Pattern | Clients | Trials | Mean updates/s | Sample SD |", "| --- | --- | --- | --- | --- | --- |"]
    for engine in ENGINES:
        for mode in MODES:
            for clients in CLIENTS:
                values = [t["updates_per_second"] for t in result["trials"]
                          if (t["engine"], t["mode"], t["clients"]) == (engine, mode, clients)]
                if len(values) != result["config"]["rounds"]:
                    raise ValueError("Missing trials")
                stats = describe(values)
                lines.append(f"| {engine} | {mode} | {clients} | {len(values)} | {stats['mean']:.2f} | {stats['sample_sd']:.2f} |")
    return "\n".join(lines) + "\n"


def run(config, total, output):
    config.validate()
    streams(config.rows, total, 4, "disjoint")
    if os.environ.get("DB_NAME") != "engine_lab":
        raise ValueError("Only the dedicated engine_lab database is allowed")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-writes-" + uuid.uuid4().hex[:8]
    directory = output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    rows = generate_rows(config)
    result = {"format_version": 1, "experiment": "concurrent_updates", "run_id": run_id,
              "status": "running", "config": asdict(config), "updates_per_trial": total,
              "clients": CLIENTS, "modes": MODES, "dataset_sha256": dataset_digest(rows),
              "source_sha256": source_fingerprint(), "runtime": runtime_metadata(), "trials": [],
              "limitations": ["same server reused", "unequal durability", "one CPU Python client",
                              "short fixed-work bursts, not sustained saturation", "warm data", "no retry policy"]}
    save_json(directory / "results.json", result)
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0)", (LOCK_NAME,))
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError("Another benchmark owns the lock")
                configure(cursor)
                cursor.execute("SELECT VERSION()")
                result["server_version"] = cursor.fetchone()[0]
                if "MariaDB" not in result["server_version"]:
                    raise RuntimeError("MariaDB required")
                cursor.execute("SHOW ENGINES")
                engines = {r[0].lower(): r[1].upper() for r in cursor.fetchall()}
                if any(engines.get(e.lower()) not in ("YES", "DEFAULT") for e in ENGINES):
                    raise RuntimeError("All five engines required")
                result["global_variables"] = variables(cursor, "global")
                result["session_variables"] = variables(cursor, "session")
            conditions = [(mode, clients) for mode in MODES for clients in CLIENTS]
            for round_index, order in enumerate(engine_schedule(config.seed, config.rounds)):
                # Rotate condition order too; five rounds do not perfectly balance six conditions.
                ordered = conditions[round_index % 6:] + conditions[:round_index % 6]
                for engine in order:
                    for position, (mode, clients) in enumerate(ordered):
                        print(f"Round {round_index + 1}/{config.rounds}: {engine} {mode} clients={clients}", flush=True)
                        item = trial(connection, engine, config, rows, clients, mode, total)
                        item.update(round=round_index + 1, condition_position=position + 1)
                        result["trials"].append(item)
                        save_json(directory / "results.json", result)
                        if item["status"] != "completed":
                            raise RuntimeError("A worker failed; partial results saved, no success report")
        result["status"] = "completed"
        summary = report(result)
        (directory / "summary.md").write_text(summary, encoding="utf-8")
        save_json(directory / "results.json", result)
        print(summary, "Saved:", directory)
    except Exception as error:
        result.update(status="failed", error_type=type(error).__name__)
        (directory / "summary.md").unlink(missing_ok=True)
        save_json(directory / "results.json", result)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--updates", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("/results"))
    args = parser.parse_args()
    try:
        run(Config(rows=args.rows, rounds=args.rounds), args.updates, args.output)
    except Exception as error:
        print("FAILED:", str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
