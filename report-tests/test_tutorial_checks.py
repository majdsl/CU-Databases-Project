"""Preserve exact updates and attributable, honest tutorial observations."""
import threading
import unittest
from unittest.mock import Mock

from scripts import tutorial_checks as tutorial


def writer(start='2026-10-28 12:00:00.000000', end='2026-10-28 12:00:01.000000'):
    return dict(engine='aria', row_id=1, updates=3, elapsed_seconds=1.0,
                server_started_at=start, server_finished_at=end)


class TutorialObservationTests(unittest.TestCase):
    def test_counter_presence_and_values_are_required(self):
        actual = tutorial.parse_lock_counters('Innodb_row_lock_waits\t20\nTable_locks_waited\t10')
        self.assertEqual(actual, dict(Table_locks_waited=10, Innodb_row_lock_waits=20))
        for output in ('', 'Table_locks_waited\t0',
                       'Table_locks_waited\t0\nTable_locks_waited\t1\nInnodb_row_lock_waits\t2',
                       'Table_locks_waited\t-1\nInnodb_row_lock_waits\t2',
                       'Table_locks_waited\tNaN\nInnodb_row_lock_waits\t2',
                       'Table_locks_waited\t1.0\nInnodb_row_lock_waits\t2',
                       'Other_counter\t0\nInnodb_row_lock_waits\t2',
                       'Table_locks_waited\t0\textra\nInnodb_row_lock_waits\t2'):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                tutorial.parse_lock_counters(output)

    def test_counter_delta_rejects_reset_missing_and_noninteger_values(self):
        before = dict(Table_locks_waited=10, Innodb_row_lock_waits=20)
        after = dict(Table_locks_waited=13, Innodb_row_lock_waits=25)
        self.assertEqual(tutorial.lock_counter_delta(before, after),
                         dict(Table_locks_waited=3, Innodb_row_lock_waits=5))
        self.assertEqual(tutorial.lock_counter_delta(before, before),
                         dict(Table_locks_waited=0, Innodb_row_lock_waits=0))
        for changed in (dict(Table_locks_waited=9, Innodb_row_lock_waits=25),
                        dict(Table_locks_waited=13),
                        dict(Table_locks_waited=True, Innodb_row_lock_waits=25),
                        dict(Table_locks_waited=13.0, Innodb_row_lock_waits=25)):
            with self.subTest(after=changed), self.assertRaises(RuntimeError):
                tutorial.lock_counter_delta(before, changed)

    def test_overlap_uses_server_intervals_and_accepts_nonoverlap(self):
        first = writer()
        second = writer('2026-10-28 12:00:00.500000', '2026-10-28 12:00:01.500000')
        self.assertEqual(tutorial.server_overlap([first, second])['seconds'], .5)
        self.assertTrue(tutorial.server_overlap([first, second])['observed'])
        for start, end in (('2026-10-28 12:00:01.000000', '2026-10-28 12:00:02.000000'),
                           ('2026-10-28 12:00:02.000000', '2026-10-28 12:00:03.000000')):
            result = tutorial.server_overlap([first, writer(start, end)])
            self.assertEqual(result['seconds'], 0)
            self.assertFalse(result['observed'])

    def test_server_interval_rejects_invalid_and_inconsistent_timings(self):
        changes = ({'server_started_at': 'not a timestamp'},
                   {'server_finished_at': '2026-10-28 11:59:59.000000'},
                   {'server_finished_at': '2026-10-28 12:00:00.000000'},
                   {'server_started_at': '2026-10-28 12:00:00.000000+00:00'},
                   {'elapsed_seconds': 2.0}, {'elapsed_seconds': float('nan')})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                tutorial.server_interval(dict(writer(), **change))

    def test_hammer_requires_sql_timestamps(self):
        sql = Mock(return_value='aria\t1\t3\t1.000000\t3\t2026-10-28 12:00:00.000000\t2026-10-28 12:00:01.000000')
        checks = tutorial.TutorialChecks(sql, Mock())
        actual = checks.hammer('aria', 1)
        self.assertEqual(actual['updates'], 3)
        self.assertEqual(actual['server_started_at'], writer()['server_started_at'])
        sql.return_value = 'aria\t1\t3\t1.000000\t3'
        with self.assertRaisesRegex(RuntimeError, 'Unexpected writer result'):
            checks.hammer('aria', 1)

    def test_invalid_writer_inputs_rejected_before_sql(self):
        sql = Mock()
        checks = tutorial.TutorialChecks(sql, Mock())
        for engine, row, seconds in (('not_an_engine', 1, 1), ('aria', True, 1),
                                     ('aria', 1, 0), ('aria', 1, 61),
                                     ('aria', 1, '1; DROP TABLE x')):
            with self.subTest(engine=engine, row=row, seconds=seconds), self.assertRaises(RuntimeError):
                checks.hammer(engine, row, seconds)
        with self.assertRaises(RuntimeError):
            checks.concurrent_writes('not_an_engine', False)
        sql.assert_not_called()

    def test_each_concurrent_case_has_counter_delta_and_exact_update_checks(self):
        for same_row in (False, True):
            for corrupt_total in (False, True):
                with self.subTest(same_row=same_row, corrupt_total=corrupt_total):
                    hits = {1: 7, 2: 11}
                    guard = threading.Lock()
                    snapshots = iter(('Table_locks_waited\t10\nInnodb_row_lock_waits\t20',
                                      'Table_locks_waited\t13\nInnodb_row_lock_waits\t25'))

                    def sql(text):
                        if text == tutorial.LOCK_STATUS_SQL:
                            return next(snapshots)
                        row = int(text.rsplit('=', 1)[1].rstrip(';'))
                        with guard:
                            return str(hits[row])

                    def hammer(engine, row):
                        with guard:
                            hits[row] += 2 if corrupt_total else 3
                        return dict(writer(), engine=engine, row_id=row)

                    checks = tutorial.TutorialChecks(sql, Mock())
                    checks.hammer = hammer
                    if corrupt_total:
                        with self.assertRaisesRegex(RuntimeError, 'lost or miscounted'):
                            checks.concurrent_writes('aria', same_row)
                    else:
                        result = checks.concurrent_writes('aria', same_row)
                        self.assertEqual(result['lock_delta'],
                                         dict(Table_locks_waited=3, Innodb_row_lock_waits=5))
                        self.assertEqual(result['server_overlap']['seconds'], 1)
                        self.assertEqual(result['lock_before']['Table_locks_waited'], 10)
                        self.assertEqual(result['lock_after']['Innodb_row_lock_waits'], 25)


if __name__ == '__main__':
    unittest.main()
