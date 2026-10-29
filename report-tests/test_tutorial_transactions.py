"""Transaction teaching checks must reject incomplete or changed SQL observations."""
import unittest
from unittest.mock import Mock

from scripts.tutorial_transactions import COMMON_ENGINES, PHASES, check_transactions, parse_results


def output(engines):
    rows = []
    for engine in engines:
        values = (engine.upper(), '1:100,2:100', '1:125,2:75',
                  '1:100,2:100' if engine in ('innodb', 'rocksdb') else '1:125,2:75',
                  '1:125,2:75')
        rows.extend('\t'.join((engine, phase, value)) for phase, value in zip(PHASES, values))
    return '\n'.join(rows)


class TransactionTutorialTests(unittest.TestCase):
    def test_real_source_paths_and_engine_scope(self):
        for rocks in (False, True):
            with self.subTest(rocks=rocks):
                source = Mock(side_effect=[output(COMMON_ENGINES), output(('rocksdb',))])
                results = check_transactions(source, rocks)
                self.assertEqual([r['engine'] for r in results],
                                 list(COMMON_ENGINES)+(['rocksdb'] if rocks else []))
                self.assertEqual([c.args[0] for c in source.call_args_list],
                                 ['05b-transactions.sql']+(['05c-myrocks-transactions.sql'] if rocks else []))
                self.assertEqual([r['engine'] for r in results if r['rollback_restored']],
                                 ['innodb']+(['rocksdb'] if rocks else []))

    def test_wrong_engine_and_changed_semantics_rejected(self):
        good = output(COMMON_ENGINES)
        mutations = (
            good.replace('innodb\tengine\tINNODB', 'innodb\tengine\tAria'),
            good.replace('innodb\tafter_rollback\t1:100,2:100', 'innodb\tafter_rollback\t1:125,2:75'),
            good.replace('aria\tafter_rollback\t1:125,2:75', 'aria\tafter_rollback\t1:100,2:100'),
            good.replace('memory\tafter_commit\t1:125,2:75', 'memory\tafter_commit\t1:100,2:100'),
            good.replace('myisam\tduring\t1:125,2:75', 'myisam\tduring\t1:125,2:74'),
        )
        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(RuntimeError):
                    parse_results(changed, COMMON_ENGINES)

    def test_missing_duplicate_or_malformed_observations_rejected(self):
        good = output(COMMON_ENGINES)
        mutations = ('\n'.join(good.splitlines()[1:]), good+'\n'+good.splitlines()[0],
                     good+'\nunrecognized', good.replace('aria\tbefore', 'unknown\tbefore'),
                     good.replace('aria\tbefore', 'aria\tunknown'))
        for changed in mutations:
            with self.subTest(changed=changed):
                with self.assertRaises(RuntimeError):
                    parse_results(changed, COMMON_ENGINES)


if __name__ == '__main__':
    unittest.main()
