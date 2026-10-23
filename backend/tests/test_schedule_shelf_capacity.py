"""Exhausted waiting cards are hidden, durable, and never bypass live capacity."""
import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from tests import test_schedule_quotas as quotas


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class ShelfCapacityDatabaseTests(unittest.TestCase):
    setUp=quotas.QuotaDatabaseTests.setUp
    setUp_base=quotas.QuotaDatabaseTests.setUp_base
    connect=quotas.QuotaDatabaseTests.connect
    tearDown=quotas.QuotaDatabaseTests.tearDown
    post=quotas.QuotaDatabaseTests.post
    confirm=quotas.QuotaDatabaseTests.confirm
    availability=quotas.QuotaDatabaseTests.availability
    record=quotas.QuotaDatabaseTests.record
    save=quotas.QuotaDatabaseTests.save
    board=quotas.QuotaDatabaseTests.board
    assign=quotas.QuotaDatabaseTests.assign
    calculate=quotas.QuotaDatabaseTests.calculate
    dispatch=quotas.QuotaDatabaseTests.dispatch

    def edits(self,mode,sid):
        row=next(r for r in self.board(mode)['rows'] if r['station_id']==sid)
        return [dict(station_id=sid,column_key=k,revision=c['revision']) for k,c in row['cells'].items()
                if c['status'] in ('assigned','unassigned')]

    def place(self,mode,card,sid):
        return self.dispatch(mode,'place',shelf_id=card['id'],revision=card['revision'],cells=self.edits(mode,sid))

    def test_full_field_group_disappears_from_both_boards_and_rejects_stale_placement_without_displacing_others(self):
        groups=self.confirm().json['groups'];field=[g for g in groups if g['mode']=='offline']
        ids=sorted(p['id'] for p in field[0]['members'])
        card=next(c for c in self.board()['shelf'] if sorted(c['ids'])==ids)
        for sid in (1,3): self.assertEqual(self.assign(field[0],sid).status_code,200)
        self.assertEqual(self.assign(field[1],2).status_code,200)
        for mode in ('offline','annual'):
            before=self.board(mode)
            self.assertFalse(any(sorted(c['ids'])==ids for c in before['shelf']))
            self.cur.execute('SELECT count(*) AS n FROM inspection_schedule_shelf_events');events=self.cur.fetchone()['n']
            result=self.place(mode,card,2)
            self.assertEqual(result.status_code,409,result.json)
            self.assertIn('待派站数已为0',result.json['error'])
            self.assertEqual(self.board(mode)['rows'],before['rows'])
            self.cur.execute('SELECT count(*) AS n FROM inspection_schedule_shelf_events');self.assertEqual(self.cur.fetchone()['n'],events)
        self.cur.execute('SELECT status FROM inspection_schedule_shelf WHERE id=%s',(card['id'],))
        self.assertEqual(self.cur.fetchone()['status'],'waiting','hide intent without deleting or consuming it')

    def test_quarter_and_annual_station_union_consumes_shared_slots_and_parking_restores_capacity(self):
        groups=self.confirm().json['groups'];field=next(g for g in groups if g['mode']=='offline')
        ids=sorted(p['id'] for p in field['members'])
        self.assertEqual(self.assign(field,1).status_code,200)
        for sid in (1,3):
            result=self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
                scheduled_date='2026-10-19',inspector_ids=ids,cells=self.edits('annual',sid)))
            self.assertEqual(result.status_code,200,result.json)
        for mode in ('offline','annual'):
            self.assertFalse(any(sorted(c['ids'])==ids for c in self.board(mode)['shelf']))
        # Removing just the quarterly half of a linked station must not free a
        # slot until its annual intent is removed too (normal dispatch links both).
        parked=self.dispatch('annual','park',cells=self.edits('annual',3))
        self.assertEqual(parked.status_code,200,parked.json)
        for mode in ('offline','annual'):
            card=next(c for c in self.board(mode)['shelf'] if sorted(c['ids'])==ids)
            self.assertEqual((card['assigned'],card['remaining']),(1,1))

    def test_video_card_hides_at_three_stations_and_returns_after_quota_increase_or_clear(self):
        video=next(g for g in self.confirm().json['groups'] if g['mode']=='online')
        person=video['members'][0];uid=person['id'];single=dict(video,members=[person])
        card=next(c for c in self.board('online')['shelf'] if c['ids']==[uid])
        for sid in (1,2,5): self.assertEqual(self.assign(single,sid).status_code,200)
        self.assertFalse(any(c['ids']==[uid] for c in self.board('online')['shelf']))
        self.assertEqual(self.place('online',card,1).status_code,409)
        self.assertEqual(self.calculate(online=4).status_code,200)
        current=next(c for c in self.board('online')['shelf'] if c['ids']==[uid])
        self.assertEqual(current['id'],card['id'])
        self.assertEqual(current['remaining'],1)
        cleared=self.dispatch('online','clear_today',board_token=self.board('online')['board_token'])
        self.assertEqual(cleared.status_code,200,cleared.json)
        self.assertEqual(next(c for c in cleared.json['board']['shelf'] if c['ids']==[uid])['remaining'],4)

    def test_lower_target_hides_existing_overquota_intent_without_rewriting_plans(self):
        field=next(g for g in self.confirm().json['groups'] if g['mode']=='offline')
        ids=sorted(p['id'] for p in field['members'])
        for sid in (1,3): self.assertEqual(self.assign(field,sid).status_code,200)
        before=self.board()['rows']
        self.assertEqual(self.calculate(offline=1).status_code,200)
        self.assertEqual(self.board()['rows'],before)
        self.assertFalse(any(sorted(c['ids'])==ids for c in self.board()['shelf']))
        self.assertEqual(self.calculate(offline=3,revision=1).status_code,200)
        self.assertEqual(next(c for c in self.board()['shelf'] if sorted(c['ids'])==ids)['remaining'],1)

    def test_different_duplicate_cards_racing_for_last_slot_only_one_commits(self):
        video=next(g for g in self.confirm().json['groups'] if g['mode']=='online')
        p=video['members'][0];uid=p['id'];single=dict(video,members=[p])
        for sid in (1,2): self.assertEqual(self.assign(single,sid).status_code,200)
        self.cur.execute("INSERT INTO stations(id,region,station_name) VALUES(6,'松金片区','金发')")
        original=next(c for c in self.board('online')['shelf'] if c['ids']==[uid])
        self.cur.execute("""INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,
            source_station_name,source_column_key) VALUES('online','2026-10-19',%s,'重复卡','测试站','row') RETURNING id,revision""",(json.dumps([uid]),))
        duplicate=dict(self.cur.fetchone());self.admin.commit()
        bodies=[dict(mode='online',year=2026,month=10,action='place',shelf_id=card['id'],
                     revision=card['revision'],cells=self.edits('online',sid)) for card,sid in ((original,5),(duplicate,6))]
        def submit(body):
            return self.client.application.test_client().post('/api/inspection-schedule/dispatch',json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit,bodies)),[200,409])
        self.assertFalse(any(c['ids']==[uid] for c in self.board('online')['shelf']))
        self.cur.execute("SELECT count(DISTINCT station_id) AS n FROM inspection_schedule_cells WHERE mode='online' AND scheduled_date='2026-10-19' AND inspector_ids @> %s::jsonb",(json.dumps([uid]),))
        self.assertEqual(self.cur.fetchone()['n'],3)
