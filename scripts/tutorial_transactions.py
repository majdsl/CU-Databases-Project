"""Validate the real tutorial SQL's deterministic rollback and commit outcomes."""

COMMON_ENGINES = ('innodb', 'aria', 'myisam', 'memory')
PHASES = ('engine', 'before', 'during', 'after_rollback', 'after_commit')
INITIAL = '1:100,2:100'
TRANSFERRED = '1:125,2:75'


def parse_results(output, engines):
    """Reject missing, duplicated or surprising outcomes, including substitution."""
    observed = {}
    for line in output.splitlines():
        cells = line.split('\t')
        if len(cells) != 3:
            raise RuntimeError('Unexpected transaction tutorial result')
        engine, phase, value = cells
        if engine not in engines or phase not in PHASES or (engine, phase) in observed:
            raise RuntimeError('Unexpected or duplicate transaction tutorial observation')
        observed[engine, phase] = value
    expected_keys = {(engine, phase) for engine in engines for phase in PHASES}
    if set(observed) != expected_keys:
        raise RuntimeError('Incomplete transaction tutorial observations')
    results = []
    for engine in engines:
        transactional = engine in ('innodb', 'rocksdb')
        expected = dict(engine=engine, before=INITIAL, during=TRANSFERRED,
                        after_rollback=INITIAL if transactional else TRANSFERRED,
                        after_commit=TRANSFERRED)
        for phase, value in expected.items():
            actual = observed[engine, phase]
            if (actual.lower() if phase == 'engine' else actual) != value:
                raise RuntimeError('Unexpected transaction tutorial outcome: '+engine+'/'+phase)
        results.append(dict(engine=engine, rollback_restored=transactional,
                            observations={phase: observed[engine, phase] for phase in PHASES}))
    return results


def check_transactions(source, rocks):
    """Source the same files a reader runs, using the driver's guarded SQL client."""
    results = parse_results(source('05b-transactions.sql'), COMMON_ENGINES)
    if rocks:
        results.extend(parse_results(source('05c-myrocks-transactions.sql'), ('rocksdb',)))
    return results
