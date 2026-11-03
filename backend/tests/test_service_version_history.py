"""Real PostgreSQL correction tests; only disposable full clones are permitted."""
import os
import unittest
from datetime import date
from unittest.mock import patch

import app as api
import checklist_versions as editions
from checklist_service_history import correct_history, REASON
from service_report_data import serialize, onsite_category, onsite_stage
from service_report_analysis import read_phrases, normalize_settings


class ServiceFieldTests(unittest.TestCase):
    def test_both_schemas_and_field_precedence(self):
        self.assertEqual(onsite_category({'项目':'新项目','考察类别区域':'旧项目'}),'新项目')
        self.assertEqual(onsite_stage({'内容':'新内容','考察类别项目':'旧内容'}),'新内容')
        self.assertEqual(onsite_category({'考察类别区域':'旧项目'}),'旧项目')
        self.assertEqual(onsite_stage({'考察类别项目':'旧内容'}),'旧内容')
        catalog=[{'key':'onsite:11039','mode':'onsite','external_standard_id':'11039',
            'fields':{'项目':'重点工作（40分）','内容':'活动学习（10分）'}}]
        rows=serialize([{'id':8,'station_id':1,'standard_id':11039,'description':'未完成宣贯'}],catalog)
        self.assertEqual(rows[0]['category'],'重点工作')
        self.assertEqual(rows[0]['content'],'活动学习（10分）')
        self.assertEqual(read_phrases(None,catalog,normalize_settings({})),{'onsite:11039':'活动学习（10分）'})


@unittest.skipUnless(os.getenv('CHECKLIST_VERSION_DB_TEST')=='1','requires isolated PostgreSQL clone')
class ServiceHistoryTests(unittest.TestCase):
    def setUp(self):
        if not os.getenv('DB_NAME','').endswith('_test'):
            raise RuntimeError('Refusing writes to a business database')
        self.conn=api.get_db_connection();self.cur=self.conn.cursor()
        self.cur.execute("SELECT id FROM inspection_tables WHERE table_name='现场检查明细表（现场）'")
        self.family=self.cur.fetchone()['id']
        self.cur.execute('SELECT id,version_number FROM inspection_checklist_versions WHERE inspection_table_id=%s',(self.family,))
        self.versions={r['version_number']:r['id'] for r in self.cur.fetchall()}
        self.cur.execute('SELECT id FROM stations ORDER BY id LIMIT 1');self.station=self.cur.fetchone()['id']
        # Recreate the legacy import error only inside this rollback-only fixture.
        self.cur.execute('ALTER TABLE inspections DISABLE TRIGGER checklist_record_version')
        self.cur.execute('ALTER TABLE issues DISABLE TRIGGER checklist_record_version')
        self.records=[];self.targets=[]
        for standards in ((11039,), (11000,11039)):
            self.cur.execute('''INSERT INTO inspections(station_id,inspector_id,inspection_table_id,inspection_date,checklist_version_id)
                VALUES(%s,1,%s,'2026-10-15',%s) RETURNING id''',(self.station,self.family,self.versions[1]))
            record=self.cur.fetchone()['id'];self.records.append(record)
            for standard in standards:
                self.cur.execute('''INSERT INTO issues(inspection_id,station_id,inspection_table_id,standard_id,
                    checklist_version_id,standard_detail_text,description,photo_path)
                    VALUES(%s,%s,%s,%s,%s,'考察类别区域：旧字段','历史说明','tests/never-read.jpg') RETURNING id''',
                    (record,self.station,self.family,standard,self.versions[1]))
                issue=self.cur.fetchone()['id']
                if standard==11039:self.targets.append(issue)
        self.cur.execute('ALTER TABLE inspections ENABLE TRIGGER checklist_record_version')
        self.cur.execute('ALTER TABLE issues ENABLE TRIGGER checklist_record_version')
        self.cur.execute("DELETE FROM checklist_version_events WHERE action='纠正新版规范历史归属' AND detail->>'reason'=%s",(REASON,))
        self.cur.execute('SAVEPOINT fixture')

    def tearDown(self):
        self.conn.rollback();self.cur.close();self.conn.close()

    def snapshot(self):
        self.cur.execute('SELECT to_jsonb(i)-\'checklist_version_id\'-\'standard_detail_text\' AS data FROM issues i WHERE id=ANY(%s) ORDER BY id',(self.targets,))
        return [r['data'] for r in self.cur.fetchall()]

    def test_correction_preserves_lifecycle_mixed_record_and_version_filters(self):
        before=self.snapshot()
        self.cur.execute('SELECT count(*) AS n FROM inspection_issue_flow_history');flow_count=self.cur.fetchone()['n']
        correct_history(self.cur)
        self.assertEqual(self.snapshot(),before)
        self.cur.execute('SELECT count(*) AS n FROM inspection_issue_flow_history');self.assertEqual(self.cur.fetchone()['n'],flow_count)
        self.cur.execute('SELECT checklist_version_id,standard_detail_text FROM issues WHERE id=ANY(%s)',(self.targets,))
        for row in self.cur.fetchall():
            self.assertEqual(row['checklist_version_id'],self.versions[2])
            self.assertTrue(row['standard_detail_text'].startswith('项目：'))
            self.assertIn('检查方式：',row['standard_detail_text']);self.assertNotIn('考察类别',row['standard_detail_text'])
        rows=[{'id':i,'inspection_table_name':'现场检查明细表（现场）'} for i in self.records]
        editions.attach_rows(self.cur,rows,'inspections')
        self.assertTrue(rows[0]['inspection_table_display_name'].endswith(' · v2'))
        self.assertTrue(rows[1]['inspection_table_display_name'].endswith(' · v1 / v2'))
        for version,expected in ((1,[self.records[1]]),(2,self.records)):
            clauses=['ins.id=ANY(%s)'];params=[self.records]
            editions.append_filter(clauses,params,[f'现场检查明细表（现场） · v{version}'],version_column='ins.checklist_version_id')
            self.cur.execute('SELECT ins.id FROM inspections ins JOIN inspection_tables t ON t.id=ins.inspection_table_id WHERE '+' AND '.join(clauses)+' ORDER BY ins.id',params)
            self.assertEqual([r['id'] for r in self.cur.fetchall()],expected)
        self.cur.execute('SELECT count(*) AS n FROM checklist_record_version_corrections');count=self.cur.fetchone()['n']
        correct_history(self.cur)
        self.cur.execute('SELECT count(*) AS n FROM checklist_record_version_corrections');self.assertEqual(self.cur.fetchone()['n'],count)
        # Ordinary editing still cannot bypass historical version protection.
        with self.assertRaises(Exception):
            self.cur.execute('UPDATE issues SET checklist_version_id=%s WHERE id=%s',(self.versions[1],self.targets[0]))

    def test_failure_rolls_back_archives_data_and_trigger_disable(self):
        before=self.snapshot();cur=self.cur
        class FailingCursor:
            def execute(self,query,params=None):
                if isinstance(query,str) and query.startswith('UPDATE inspections SET checklist_version_id'):
                    raise RuntimeError('simulated migration failure')
                return cur.execute(query,params)
            def __getattr__(self,key):return getattr(cur,key)
        with self.assertRaisesRegex(RuntimeError,'simulated'):
            correct_history(FailingCursor())
        self.cur.execute('ROLLBACK TO SAVEPOINT fixture')
        self.assertEqual(self.snapshot(),before)
        self.cur.execute("SELECT tgenabled FROM pg_trigger WHERE tgname='checklist_record_version' AND tgrelid IN ('issues'::regclass,'inspections'::regclass)")
        self.assertTrue(all(r['tgenabled']=='O' for r in self.cur.fetchall()))

    def test_service_catalog_and_input_queries_read_both_versions_without_paid_calls(self):
        correct_history(self.cur)
        user={'id':1,'role':'root'}
        with patch('service_report_analysis.run_ai',side_effect=AssertionError('read must not call AI')):
            catalog=api.fetch_service_report_catalog(self.cur,user)
            by_id={s['external_standard_id']:s for s in catalog}
            self.assertIn('考察类别区域',by_id['11000']['fields'])
            self.assertIn('项目',by_id['11039']['fields'])
            self.assertNotIn('考察类别区域',by_id['11039']['fields'])
            # Switch only the fixture issues to approved, then exercise real scope SQL.
            self.cur.execute("UPDATE issues SET audit_status='approved' WHERE inspection_id=ANY(%s)",(self.records,))
            raw,_,_=api.fetch_service_report_inputs(self.cur,user,date(2026,10,1),date(2026,11,1))
            rows=serialize(raw,catalog)
            self.assertTrue(set(self.targets)<={r['issue_id'] for r in rows})
            self.cur.execute('SELECT id FROM issues WHERE inspection_id=%s AND standard_id=11000',(self.records[1],))
            old=self.cur.fetchone()['id'];self.assertIn(old,{r['issue_id'] for r in rows})
            self.cur.execute('UPDATE inspection_tables SET active_version_id=%s WHERE id=%s',(self.versions[1],self.family))
            editions.report_guard(self.cur,['现场检查明细表（现场）'])
            rows_again,_,_=api.fetch_service_report_inputs(self.cur,user,date(2026,10,1),date(2026,11,1))
            self.assertTrue(set(self.targets)<={r['id'] for r in rows_again})
            self.cur.execute('''INSERT INTO inspection_checklist_versions(inspection_table_id,version_number,version_name,fields)
                VALUES(%s,99,'未知后续版本','[]') RETURNING id''',(self.family,))
            future=self.cur.fetchone()['id']
            self.cur.execute('UPDATE inspection_tables SET active_version_id=%s WHERE id=%s',(future,self.family))
            with self.assertRaisesRegex(ValueError,'版本与报告模板不兼容'):
                editions.report_guard(self.cur,['现场检查明细表（现场）'])
