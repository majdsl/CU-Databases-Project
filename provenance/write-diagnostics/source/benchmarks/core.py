"""Pure experiment logic: no database access or dependencies."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
import statistics

ENGINES = ("InnoDB", "Aria", "MyISAM", "MEMORY", "ROCKSDB")


@dataclass(frozen=True)
class Config:
    rows: int = 10_000
    rounds: int = 5
    lookups: int = 200
    scans: int = 5
    batch_size: int = 500
    seed: int = 20260923

    def validate(self):
        for name, value in asdict(self).items():
            if type(value) is not int:
                raise ValueError(name + " must be an integer")
        if not 100 <= self.rows <= 200_000:
            raise ValueError("rows must be between 100 and 200000 for this baseline")
        if self.rounds not in (5, 10, 15, 20):
            raise ValueError("rounds must be 5, 10, 15 or 20 for balanced engine order")
        if not 10 <= self.lookups <= 10_000 or not 2 <= self.scans <= 100:
            raise ValueError("lookups must be 10..10000 and scans 2..100")
        if not 1 <= self.batch_size <= 1000:
            raise ValueError("batch_size must be 1..1000")


def generate_rows(config):
    """Synthetic flight events. These are not observations of real flights."""
    config.validate()
    rng = random.Random(config.seed)
    return [
        (i, rng.randint(1, 500), 1767225600 + rng.randrange(365 * 86400),
         rng.randint(-15, 180), rng.randint(1000, 500000), rng.randint(1, 6),
         hashlib.sha256((str(config.seed) + ":" + str(i)).encode()).hexdigest())
        for i in range(1, config.rows + 1)
    ]


def row_bytes(row):
    return (json.dumps(list(row), ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def dataset_digest(rows):
    result = hashlib.sha256()
    for row in rows:
        result.update(row_bytes(row))
    return result.hexdigest()


def engine_schedule(seed, rounds):
    if rounds < 5 or rounds % 5:
        raise ValueError("engine schedule requires a multiple of five rounds")
    rng = random.Random(seed)
    schedule = []
    for _ in range(rounds // 5):
        base = list(ENGINES)
        rng.shuffle(base)
        schedule.extend(base[i:] + base[:i] for i in range(5))
    return schedule


def lookup_ids(seed, round_number, rows, count):
    rng = random.Random(seed + 1_000_003 * (round_number + 1))
    return [rng.randint(1, rows) for _ in range(count)]


def expected_scan(rows):
    return (len(rows), sum(row[3] for row in rows),
            sum(row[4] * row[5] for row in rows))


def describe(values):
    """p95 uses the nearest-rank rule; standard deviation is sample SD."""
    if not values or any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("expected finite nonnegative measurements")
    values = sorted(values)
    return {"n": len(values), "mean": statistics.mean(values),
            "median": statistics.median(values),
            "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
            "min": values[0], "max": values[-1],
            "p95_nearest_rank": values[math.ceil(.95 * len(values)) - 1]}
