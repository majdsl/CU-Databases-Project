"""Four-engine integration check, not a performance benchmark."""
import os
from pathlib import Path
import sys
import pymysql

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "sql"
ENGINES = ("InnoDB", "Aria", "MyISAM", "MEMORY")

def main():
    with pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        charset="utf8mb4", autocommit=True, connect_timeout=10,
        read_timeout=30, write_timeout=30,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            if "MariaDB" not in version:
                raise RuntimeError("This project requires MariaDB.")
            print("Server:", version)
            cursor.execute("SHOW ENGINES")
            available = {row[0].lower(): row[1].upper() for row in cursor.fetchall()}
            for engine in ENGINES:
                if available.get(engine.lower()) not in {"YES", "DEFAULT"}:
                    raise RuntimeError("Required engine is unavailable: " + engine)
                # Fixed, reviewed DDL files; engine identifiers never come from user input.
                cursor.execute((SCHEMA_DIR / (engine.lower() + ".sql")).read_text())
                try:
                    cursor.execute(
                        "SELECT ENGINE FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                        ("setup_probe",),
                    )
                    actual = cursor.fetchone()
                    if actual is None or actual[0].lower() != engine.lower():
                        raise RuntimeError("Actual table engine does not match " + engine)
                    expected = ((1, "alpha"), (2, "quote's value"), (3, "gamma"))
                    cursor.executemany(
                        "INSERT INTO setup_probe (id, payload) VALUES (%s, %s)", expected,
                    )
                    cursor.execute("SELECT id, payload FROM setup_probe ORDER BY id")
                    if cursor.fetchall() != expected:
                        raise RuntimeError("Data verification failed for " + engine)
                    print("PASS:", engine, "- actual engine verified; 3 rows matched")
                finally:
                    cursor.execute("DROP TABLE setup_probe")
            print("PASS: all four engines. Setup check only; no benchmark results yet.")

if __name__ == "__main__":
    try:
        main()
    except (pymysql.MySQLError, RuntimeError, KeyError, OSError) as error:
        print("FAIL:", str(error), file=sys.stderr)
        sys.exit(1)
