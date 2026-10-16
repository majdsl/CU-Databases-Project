import copy
import os
import unittest
from unittest.mock import MagicMock, patch
from benchmarks import memory_indexes as m
from benchmarks.core import dataset_digest


class MemoryIndexTests(unittest.TestCase):
    def test_balanced_pairs_and_identical_streams(self):
        c = m.Config('full')
        schedule = m.schedule(c)
        self.assertEqual(len(schedule), 24)
        for size in c.sizes:
            for index in m.DDL:
                positions = [t['position'] for t in schedule if t['rows']==size and t['index']==index]
                self.assertEqual(positions.count(1), 3)
                self.assertEqual(positions.count(2), 3)
        for a,b in zip(schedule[::2], schedule[1::2]):
            self.assertEqual((a['round'],a['rows']), (b['round'],b['rows']))
            self.assertEqual(m.streams(c,a['rows'],a['round']),m.streams(c,b['rows'],b['round']))

    def test_known_answers_and_endpoints(self):
        rows = [(1,3,9),(2,1,4),(3,2,7)]
        self.assertEqual(m.oracle(rows, {'equality':[(2,)], 'range':[(1,3),(3,3)]}),
                         {'equality':[(1,7)], 'range':[(3,20),(1,9)]})
        for size in m.Config().sizes:
            for label, params in m.streams(m.Config(),size,1).items():
                for p in params:
                    self.assertTrue(1 <= p[0] <= p[-1] <= size)
                    self.assertEqual(p[-1]-p[0]+1, 1 if label=='equality' else int(label.split('_')[1]))

    def test_schema_changes_only_secondary_index(self):
        self.assertEqual(m.DDL['HASH'].replace('probe_k (k) USING HASH','probe_k (k) USING BTREE'),m.DDL['BTREE'])
        self.assertEqual(m.dataset(100,7),m.dataset(100,7))
        self.assertEqual(sorted(r[1] for r in m.dataset(100,7)),list(range(1,101)))

    def test_index_substitution_rejected(self):
        indexes=[{'Key_name':'PRIMARY','Column_name':'id','Index_type':'BTREE'},
                 {'Key_name':'probe_k','Column_name':'k','Index_type':'HASH'}]
        m.verify_indexes(indexes,'HASH')
        with self.assertRaises(RuntimeError):m.verify_indexes(indexes,'BTREE')

    def test_existing_table_never_changed(self):
        connection=MagicMock(); cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=('memory_index_probe',)
        with self.assertRaises(RuntimeError):m.trial(connection,m.Config(),m.schedule(m.Config())[0])
        self.assertEqual(cursor.execute.call_count,1)

    def test_corrupt_and_missing_loaded_rows_rejected(self):
        rows=[(1,2,3),(2,1,4)]
        for batches in ([[rows[0]],[]], [[(1,2,99),rows[1]],[]], [rows+[(3,3,3)],[]]):
            cursor=MagicMock();cursor.fetchmany.side_effect=batches
            with self.assertRaises(RuntimeError):m.verify_rows(cursor,rows)

    def fixture(self):
        c=m.Config('smoke'); result={'config':{'mode':'smoke','seed':c.seed},'status':'completed','schedule':m.schedule(c),'trials':[]}
        for item in result['schedule']:
            rows=m.dataset(item['rows'],c.seed); streams=m.streams(c,item['rows'],item['round'])
            result['trials'].append(dict(item,verified_rows=len(rows),verified_dataset_sha256=dataset_digest(rows),
                actual_indexes=[{'Key_name':'PRIMARY','Column_name':'id','Index_type':'BTREE'},
                                {'Key_name':'probe_k','Column_name':'k','Index_type':item['index']}],
                query_streams=streams,answers=m.oracle(rows,streams),load_seconds=1,
                timings_ms={label:[float(item['round'])]*c.samples for label in m.QUERIES}))
        return result

    def test_statistics_use_trials_and_reject_incomplete_evidence(self):
        r=self.fixture(); s=m.summarize(r)
        self.assertEqual(s['1000']['HASH']['equality']['n'],2)
        self.assertEqual(s['1000']['HASH']['equality']['mean'],1.5)
        for change in ('status','trial','digest','sample','answer','stream'):
            bad=copy.deepcopy(r)
            if change=='status':bad['status']='failed'
            if change=='trial':bad['trials'].pop()
            if change=='digest':bad['trials'][0]['verified_dataset_sha256']='wrong'
            if change=='sample':bad['trials'][0]['timings_ms']['equality'].pop()
            if change=='answer':bad['trials'][0]['answers']['equality'][0]=(0,0)
            if change=='stream':bad['trials'][0]['query_streams']['equality'][0]=(0,)
            with self.assertRaises(ValueError):m.summarize(bad)

    def test_wrong_database_rejected_before_connect(self):
        with patch.dict(os.environ,{'DB_NAME':'production'}):
            with self.assertRaises(ValueError):m.run(m.Config(),None,'test')

    def test_counter_reset_not_reported_as_work(self):
        cursor=MagicMock()
        with patch.object(m,'records',return_value=[]), patch.object(m,'measure'), patch.object(m,'handlers',side_effect=[{'Handler_read_key':5},{'Handler_read_key':1}]):
            with self.assertRaises(RuntimeError):m.diagnostic(cursor,m.POINT,(1,),(1,1))


if __name__=='__main__':unittest.main()
