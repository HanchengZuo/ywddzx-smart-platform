"""Shared station targets and remaining-count shelves in isolated PostgreSQL schemas."""
import os
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from flask import Flask
from unittest.mock import MagicMock
from pathlib import Path
from schedule_automation import register_schedule_automation
from tests import test_schedule_smart as smart_tests


class AuthenticationTests(unittest.TestCase):
    def test_anonymous_quota_read_never_opens_database(self):
        app=Flask(__name__);connect=MagicMock()
        register_schedule_automation(app,connect=connect,has_permission=lambda *_:True)
        self.assertEqual(app.test_client().get('/api/inspection-schedule/quotas').status_code,401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class QuotaDatabaseTests(unittest.TestCase):
    setUp=smart_tests.SmartDatabaseTests.setUp
    setUp_base=smart_tests.SmartDatabaseTests.setUp_base
    connect=smart_tests.SmartDatabaseTests.connect
    tearDown=smart_tests.SmartDatabaseTests.tearDown
    post=smart_tests.SmartDatabaseTests.post
    confirm=smart_tests.SmartDatabaseTests.confirm
    availability=smart_tests.SmartDatabaseTests.availability
    record=smart_tests.SmartDatabaseTests.record
    save=smart_tests.SmartDatabaseTests.save
    board=smart_tests.SmartDatabaseTests.board
    assign=smart_tests.SmartDatabaseTests.assign

    def calculate(self,offline=2,online=3,revision=0,**extra):
        return self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',
            strategy='replace_today',day='2026-10-19',offline_count=offline,online_count=online,
            quota_revision=revision,save_quotas=True,**extra))

    def dispatch(self,mode,action,**extra):
        return self.client.post('/api/inspection-schedule/dispatch',json=dict(mode=mode,year=2026,
            **(dict(quarter=4) if mode=='offline' else dict(month=10) if mode=='online' else {}),action=action,**extra))

    def test_quota_changes_are_shared_audited_and_read_does_not_write(self):
        before=self.client.get('/api/inspection-schedule/quotas')
        self.assertEqual((before.json['offline_count'],before.json['online_count'],before.json['revision']),(2,3,0))
        self.assertEqual(before.headers['Cache-Control'],'private, no-store')
        self.confirm()
        changed=self.calculate(offline=4,online=5)
        self.assertEqual(changed.status_code,200,changed.json)
        self.assertEqual(changed.json['quota_settings']['revision'],1)
        self.actor=dict(id=3,username='other',role='supervisor_manager')
        shared=self.client.get('/api/inspection-schedule/quotas').json
        self.assertEqual((shared['offline_count'],shared['online_count']),(4,5))
        stale=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',strategy='replace_today',quota_revision=0))
        self.assertEqual(stale.status_code,409)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_quota_events');self.assertEqual(self.cur.fetchone()['n'],1)
        self.assertEqual(self.calculate(offline=4,online=5,revision=1).status_code,200)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_quota_events');self.assertEqual(self.cur.fetchone()['n'],1)
        self.cur.execute((Path(__file__).resolve().parents[1]/'db/init/565_schedule_dispatch_quotas.sql').read_text());self.admin.commit()
        self.assertEqual(self.client.get('/api/inspection-schedule/quotas').json['offline_count'],4)

    def test_quota_permission_validation_and_audit_failure_roll_back(self):
        self.permissions.discard('edit_inspection_schedule')
        self.assertEqual(self.client.get('/api/inspection-schedule/quotas').status_code,200)
        self.assertEqual(self.calculate(offline=4).status_code,403)
        self.permissions.add('edit_inspection_schedule')
        self.assertEqual(self.calculate(offline=0).status_code,400)
        self.assertEqual(self.calculate(online=True).status_code,400)
        self.assertEqual(self.calculate(revision=99).status_code,409)
        self.cur.execute('ALTER TABLE inspection_schedule_quota_events ADD CHECK(false) NOT VALID');self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.calculate(offline=4).status_code,500)
        self.assertEqual(self.client.get('/api/inspection-schedule/quotas').json['offline_count'],2)
        self.permissions.discard('view_inspection_schedule')
        self.assertEqual(self.client.get('/api/inspection-schedule/quotas').status_code,403)

    def test_concurrent_quota_updates_cannot_silently_overwrite_the_same_revision(self):
        self.confirm()
        body=dict(action='preview',strategy='replace_today',day='2026-10-19',offline_count=4,
            online_count=3,quota_revision=0,save_quotas=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.client.application.test_client().post('/api/inspection-schedule/auto',json=body).status_code,range(2)))
        self.assertEqual(sorted(results),[200,409])

    def test_video_shelf_deduplicates_station_transfers_and_counts_whole_stations(self):
        groups=self.confirm().json['groups']
        video=next(g for g in groups if g['mode']=='online')
        uid=video['members'][0]['id']
        card=next(c for c in self.board('online')['shelf'] if c['ids']==[uid])
        self.assertEqual(card['remaining'],3)
        self.assertEqual(self.assign(dict(video,members=[video['members'][0]]),sid=1).status_code,200)
        self.assertEqual(self.assign(dict(video,members=[video['members'][0]]),sid=2).status_code,200)
        card=next(c for c in self.board('online')['shelf'] if c['ids']==[uid])
        self.assertEqual((card['assigned'],card['remaining']),(2,1),'six checklist cells are only two stations')
        self.record(station=1,table=7,inspector=uid,day='2026-10-19')
        self.assertEqual(next(c for c in self.board('online')['shelf'] if c['ids']==[uid])['remaining'],1)
        b=self.board('online');cleared=self.dispatch('online','clear_today',board_token=b['board_token'])
        self.assertEqual(cleared.status_code,200,cleared.json)
        cards=[c for c in cleared.json['board']['shelf'] if c['ids']==[uid]]
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['remaining'],2,'the started station remains assigned and consumes one slot')
        row=next(r for r in cleared.json['board']['rows'] if r['station_id']==2)
        placed=self.dispatch('online','place',shelf_id=cards[0]['id'],revision=cards[0]['revision'],
            cells=[dict(station_id=2,column_key=k,revision=c['revision']) for k,c in row['cells'].items()])
        self.assertEqual(placed.status_code,200,placed.json)
        cards=[c for c in placed.json['board']['shelf'] if c['ids']==[uid]]
        self.assertEqual(len(cards),1);self.assertEqual(cards[0]['remaining'],1)

    def test_field_and_annual_shelves_share_target_and_union_station_counts(self):
        groups=self.confirm().json['groups'];field=next(g for g in groups if g['mode']=='offline')
        ids=sorted(p['id'] for p in field['members'])
        self.assertEqual(self.assign(field,sid=1).status_code,200)
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1");self.admin.commit()
        annual=self.board('annual');row=next(r for r in annual['rows'] if r['station_id']==1)
        result=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
            inspector_ids=ids,scheduled_date='2026-10-19',cells=[dict(station_id=1,column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['status']=='unassigned']))
        self.assertEqual(result.status_code,200,result.json)
        for mode in ('offline','annual'):
            cards=[c for c in self.board(mode)['shelf'] if sorted(c['ids'])==ids]
            self.assertEqual(len(cards),1);self.assertEqual((cards[0]['assigned'],cards[0]['remaining']),(1,1))
        self.assertEqual(self.calculate(offline=4).status_code,200)
        self.assertEqual(next(c for c in self.board('annual')['shelf'] if sorted(c['ids'])==ids)['remaining'],3)
        self.assertEqual(self.assign(field,sid=3).status_code,200)
        self.assertEqual(next(c for c in self.board()['shelf'] if sorted(c['ids'])==ids)['remaining'],2)

    def test_discard_removes_all_hidden_duplicates_without_changing_board_plans(self):
        groups=self.confirm().json['groups'];field=next(g for g in groups if g['mode']=='offline')
        ids=sorted(p['id'] for p in field['members'])
        self.assign(field,sid=1);self.assign(field,sid=3)
        board=self.board();cleared=self.dispatch('offline','clear_today',board_token=board['board_token'])
        self.assertEqual(cleared.status_code,200,cleared.json)
        card=next(c for c in cleared.json['board']['shelf'] if sorted(c['ids'])==ids)
        self.assertEqual(card['remaining'],2)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_shelf WHERE status='waiting' AND inspector_ids=%s::jsonb",(json.dumps(ids),))
        self.assertGreater(self.cur.fetchone()['n'],1)
        response=self.dispatch('offline','discard',shelf_id=card['id'],revision=card['revision'])
        self.assertEqual(response.status_code,200,response.json)
        self.assertFalse(any(sorted(c['ids'])==ids for c in response.json['board']['shelf']))
        self.assertEqual(response.json['board']['rows'],cleared.json['board']['rows'])
