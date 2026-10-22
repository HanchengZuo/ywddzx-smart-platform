"""Transactional shelf and task behavior against an opt-in, isolated PostgreSQL schema."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask
from inspection_schedule_dispatch import register_schedule_dispatch
from tests import test_staff_scheduling as staff_tests
from tests import test_schedule_dispatch as dispatch_tests
from tests import test_staff_daily_teams as team_tests


class AuthenticationTests(unittest.TestCase):
    def test_anonymous_never_opens_database(self):
        app = Flask(__name__)
        connect = MagicMock()
        register_schedule_dispatch(app, connect=connect, has_permission=lambda *_: True)
        self.assertEqual(app.test_client().post('/api/inspection-schedule/dispatch', json={}).status_code, 401)
        connect.assert_not_called()


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class ShelfDatabaseTests(unittest.TestCase):
    def setUp(self):
        staff_tests.StaffDatabaseTests.setUp(self)
        for module in ('schedule_common','staff_availability','staff_daily_team_http','inspection_schedule',
                       'inspection_schedule_tasks','schedule_automation','inspection_schedule_dispatch','schedule_shelf_store'):
            clock = patch(module+'.today',return_value=date(2026,10,20))
            clock.start(); self.addCleanup(clock.stop)
    setUp_base = staff_tests.StaffDatabaseTests.setUp_base
    connect = staff_tests.StaffDatabaseTests.connect
    tearDown = staff_tests.StaffDatabaseTests.tearDown
    availability = staff_tests.StaffDatabaseTests.availability
    save = staff_tests.StaffDatabaseTests.save
    board = staff_tests.StaffDatabaseTests.board
    record = staff_tests.StaffDatabaseTests.record
    row_cells = dispatch_tests.DispatchDatabaseTests.row_cells
    video = dispatch_tests.DispatchDatabaseTests.video

    def dispatch(self, action, query=None, **extra):
        return self.client.post('/api/inspection-schedule/dispatch', json={**(query or self.query), 'action': action, **extra})

    def video_cells(self, sid, revision=0, skip=()):
        return [dict(station_id=sid,column_key=k,revision=revision) for k in ('safety','measurement','service') if k not in skip]

    def park(self, sid=1, revision=1, skip=()):
        response = self.dispatch('park', cells=self.row_cells(sid, revision, skip))
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['board']['shelf'][-1]

    def place(self, item, sid=2, revision=0, **extra):
        return self.dispatch('place', shelf_id=item['id'], revision=item['revision'], cells=self.row_cells(sid, revision), **extra)

    def test_park_immediately_clears_row_cancels_tasks_and_is_durable_and_shared(self):
        self.assertEqual(self.save().status_code, 200)
        item = self.park()
        board = self.board()
        self.assertEqual(board['shelf'], [item])
        self.assertTrue(all(c['assignees'] == [] for c in board['rows'][0]['cells'].values()))
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='cancelled'")
        self.assertEqual(self.cur.fetchone()['n'], 6)
        self.actor = dict(id=3, username='lead', role='supervisor_manager')
        self.assertEqual(self.board()['shelf'], [item])
        self.assertEqual(self.dispatch('park', cells=self.row_cells(1, 1)).status_code, 409)
        self.cur.execute('SELECT actor_id FROM inspection_schedule_shelf_events')
        self.assertEqual([r['actor_id'] for r in self.cur.fetchall()], [2])

    def test_place_fills_six_cells_and_swap_preserves_displaced_team(self):
        self.save()
        self.assertEqual(self.save(station_id=2, inspector_ids=[3]).status_code, 200)
        first = self.park()
        response = self.place(first, revision=1)
        self.assertEqual(response.status_code, 200, response.json)
        board = response.json['board']
        second = board['shelf'][0]
        self.assertEqual(second['ids'], [3])
        target = next(r for r in board['rows'] if r['station_id'] == 2)
        self.assertTrue(all([p['id'] for p in c['assignees']] == [2] for c in target['cells'].values()))
        self.assertEqual(self.place(second, sid=1, revision=2).status_code, 200)
        self.assertEqual(self.board()['shelf'], [])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'], 12)
        self.assertEqual(self.place(first, revision=2).status_code, 409)

    def test_partial_actual_record_is_never_cleared_or_moved(self):
        self.save()
        record = self.record()
        self.assertEqual(self.dispatch('park',cells=self.row_cells(1,1,skip=('odor',))).status_code,409)
        cells = self.board()['rows'][0]['cells']
        self.assertEqual(cells['odor']['status'], 'completed')
        self.assertEqual([p['id'] for p in cells['odor']['assignees']], [2])
        self.assertTrue(all(c['row_locked'] for c in cells.values()))
        self.assertEqual(self.board()['shelf'],[])
        self.assertTrue(all(c['assignees'][0]['id']==2 for c in cells.values()))
        self.cur.execute('SELECT id FROM inspections'); self.assertEqual(self.cur.fetchone()['id'], record)

    def test_video_moves_whole_row_and_cannot_be_placed_as_field(self):
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        self.assertEqual(self.video().status_code, 200)
        query = dict(mode='online', year=2026, month=10)
        self.assertEqual(self.dispatch('park',query,cells=self.video_cells(1,1)[:1]).status_code,409)
        response = self.dispatch('park', query, cells=self.video_cells(1,1))
        self.assertEqual(response.status_code, 200, response.json)
        item = response.json['board']['shelf'][0]
        self.assertEqual(len(response.json['board']['shelf']),1)
        self.assertEqual(item['source_column_key'],'row')
        self.assertTrue(all(c['status']=='unassigned' for c in response.json['board']['rows'][0]['cells'].values()))
        self.assertEqual(self.place(item).status_code, 409)
        self.assertEqual(self.dispatch('place',query,shelf_id=item['id'],revision=1,cells=self.video_cells(2)[:1]).status_code,409)
        response = self.dispatch('place', query, shelf_id=item['id'], revision=1,
                                 cells=self.video_cells(2))
        self.assertEqual(response.status_code, 200, response.json)
        cells = next(r for r in response.json['board']['rows'] if r['station_id'] == 2)['cells']
        self.assertTrue(all(c['assignees'][0]['id']==2 for c in cells.values()))
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE mode='online' AND status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],3)

    def test_clear_today_mode_date_actual_and_stale_board_boundaries(self):
        self.save()
        self.save(station_id=2)
        self.record()
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) VALUES('步雪琼','2026-10-21',true,1,1)")
        self.cur.execute("INSERT INTO staff_daily_teams SELECT '2026-10-21',assignments,revision,updated_by,updated_at FROM staff_daily_teams WHERE day='2026-10-20'")
        self.admin.commit()
        self.assertEqual(self.save(station_id=3, scheduled_date='2026-10-21').status_code, 200)
        token = self.board()['board_token']
        with patch('inspection_schedule_dispatch.today', return_value=date(2026,10,20)):
            response = self.dispatch('clear_today', board_token=token)
            self.assertEqual(response.status_code, 200, response.json)
            self.assertEqual(response.json['cleared_count'], 6)
            self.assertEqual(response.json['cleared_station_count'], 1)
            self.assertEqual(response.json['parked_count'], 1)
            self.assertEqual({c['source_station_id'] for c in response.json['board']['shelf']}, {2})
            self.assertTrue(all(c['ids']==[2] and c['plan_team']['leader_id']==2
                                for c in response.json['board']['shelf']))
            self.assertEqual(self.dispatch('clear_today', board_token=token).status_code, 409)
        self.cur.execute("SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=3")
        self.assertTrue(all(r['inspector_ids'] == [2] for r in self.cur.fetchall()))
        self.assertEqual(self.board()['rows'][0]['cells']['odor']['status'], 'completed')
        self.assertEqual(self.dispatch('clear_today', board_token=token, query=dict(mode='online',year=2025,month=10)).status_code, 400)

    def test_video_clear_does_not_touch_field(self):
        self.save()
        self.cur.execute("UPDATE staff_daily_teams SET assignments='[]'"); self.admin.commit()
        self.assertEqual(self.video(inspector_ids=[3]).status_code, 200)
        query = dict(mode='online',year=2026,month=10)
        token = self.board(query)['board_token']
        with patch('inspection_schedule_dispatch.today', return_value=date(2026,10,20)):
            response = self.dispatch('clear_today', query, board_token=token)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['cleared_count'], 3)
        self.assertEqual(response.json['parked_count'], 1)
        self.assertEqual(response.json['cleared_station_count'], 1)
        card=response.json['board']['shelf'][0]
        self.assertEqual(card['ids'],[3])
        self.assertEqual(card['source_column_key'],'row')
        self.assertTrue(all(c['status'] == 'assigned' for c in self.board()['rows'][0]['cells'].values()))
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE mode='online' AND status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],0)
        restored=self.dispatch('place',query,shelf_id=card['id'],revision=card['revision'],cells=self.video_cells(1,2))
        self.assertEqual(restored.status_code,200,restored.json)
        self.assertTrue(all(c['status']=='assigned' and c['assignees'][0]['id']==3
                            for c in restored.json['board']['rows'][0]['cells'].values()))

    def test_permissions_and_malformed_requests_do_not_write(self):
        self.save()
        self.permissions.discard('edit_inspection_schedule')
        self.assertEqual(self.dispatch('park', cells=self.row_cells(1,1)).status_code, 403)
        self.assertEqual(self.dispatch('clear_today', board_token=self.board()['board_token']).status_code,403)
        self.permissions.add('edit_inspection_schedule')
        for cells in [None, [], 123, [{}], self.row_cells(1,1)[:1]]:
            self.assertIn(self.dispatch('park', cells=cells).status_code, (400,409))
        self.assertEqual(self.dispatch('unknown').status_code, 400)
        self.cur.execute('SELECT 1 FROM inspection_schedule_shelf'); self.assertIsNone(self.cur.fetchone())

    def test_park_audit_failure_rolls_back_card_cells_tasks(self):
        self.save()
        self.cur.execute('ALTER TABLE inspection_schedule_shelf_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.dispatch('park',cells=self.row_cells(1,1)).status_code, 500)
        self.assertEqual(self.board()['shelf'], [])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'], 6)

    def test_placement_failure_rolls_back_displaced_card_and_plan(self):
        self.save(); self.save(station_id=2, inspector_ids=[3])
        item = self.park()
        self.cur.execute('ALTER TABLE inspection_schedule_events ADD CHECK(false) NOT VALID'); self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.place(item, revision=1).status_code, 500)
        self.assertEqual(self.board()['shelf'], [item])
        self.cur.execute('SELECT inspector_ids FROM inspection_schedule_cells WHERE station_id=2')
        self.assertTrue(all(r['inspector_ids'] == [3] for r in self.cur.fetchall()))

    def test_clear_failure_on_later_station_rolls_back_all_cards_and_tasks(self):
        self.save(); self.save(station_id=2)
        token = self.board()['board_token']
        self.cur.execute('ALTER TABLE inspection_schedule_events ADD CHECK(station_id<>2) NOT VALID'); self.admin.commit()
        with patch('inspection_schedule_dispatch.today', return_value=date(2026,10,20)), self.assertLogs(level='ERROR'):
            self.assertEqual(self.dispatch('clear_today',board_token=token).status_code,500)
        self.assertEqual(self.board()['shelf'], [])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],12)

    def test_concurrent_placements_only_one_wins(self):
        self.save(); item = self.park()
        def place(sid):
            return self.client.application.test_client().post('/api/inspection-schedule/dispatch', json={
                **self.query, 'action':'place', 'shelf_id':item['id'], 'revision':1, 'cells':self.row_cells(sid)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(place, [2,3])), [200,409])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'], 6)

    def test_busy_person_is_revalidated_and_card_is_retained(self):
        self.save(); item = self.park()
        self.cur.execute("UPDATE staff_availability SET available=false WHERE person_name='步雪琼'"); self.admin.commit()
        self.assertEqual(self.place(item).status_code, 409)
        self.assertEqual(self.board()['shelf'], [item])

    def test_discard_is_audited_and_sql_is_repeatable(self):
        self.save(); item = self.park()
        sql=(Path(__file__).resolve().parents[1]/'db/init/535_schedule_shelf.sql').read_text()
        self.cur.execute(sql); self.cur.execute(sql); self.admin.commit()
        self.assertEqual(self.dispatch('discard', shelf_id=item['id'], revision=1, user_id=1).status_code, 200)
        self.assertEqual(self.board()['shelf'], [])
        self.cur.execute('SELECT actor_id,action FROM inspection_schedule_shelf_events ORDER BY id DESC LIMIT 1')
        self.assertEqual(dict(self.cur.fetchone()), dict(actor_id=2,action='discarded'))

    def test_staff_group_label_survives_actual_inspection(self):
        self.save()
        self.record(inspector=2, day='2026-10-20')
        board = self.client.get('/api/staff-availability?week=2026-10-19').json
        cell = board['people'][0]['cells']['2026-10-20']
        self.assertEqual(cell['field_group_names'], ['外勤步雪琼组'])

    def test_video_partial_actual_preserved_and_full_row_conflict_rolls_back(self):
        self.cur.execute('DELETE FROM staff_daily_teams'); self.admin.commit()
        self.video()
        query = dict(mode='online',year=2026,month=10)
        parked = self.dispatch('park',query,cells=self.video_cells(1,1))
        self.assertEqual(parked.status_code,200,parked.json)
        card = parked.json['board']['shelf'][0]
        original = self.record(table=7,inspector=3)
        self.assertEqual(self.board(query)['rows'][0]['cells']['safety']['status'],'completed')
        self.cur.execute("ALTER TABLE inspection_schedule_events ADD CHECK(column_key<>'service') NOT VALID");self.admin.commit()
        with self.assertLogs(level='ERROR'):
            response = self.dispatch('place',query,shelf_id=card['id'],revision=card['revision'],cells=self.video_cells(2))
        self.assertEqual(response.status_code,500)
        self.assertEqual(self.board(query)['shelf'],[card])
        self.cur.execute('SELECT 1 FROM inspection_schedule_cells WHERE station_id=2');self.assertIsNone(self.cur.fetchone())
        self.cur.execute('SELECT id FROM inspections');self.assertEqual(self.cur.fetchone()['id'],original)

    def test_video_legacy_shelf_upgrade_keeps_audit_and_does_not_merge_different_people(self):
        for key,uid,day in [('safety',2,'2026-10-20'),('measurement',2,'2026-10-20'),('service',2,'2026-10-20'),('safety',3,'2026-10-20'),('safety',2,'2026-10-21')]:
            self.cur.execute('''INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,
              source_station_id,source_station_name,source_column_key,created_by,updated_by)
              VALUES('online',%s,%s::jsonb,'检查人',1,'沈浦泾南',%s,2,2)''',(day,f'[{uid}]',key))
        self.cur.execute("""INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,
          source_station_id,source_station_name,source_column_key) VALUES('offline','2026-10-20','[2]','外勤组',1,'沈浦泾南','row')""")
        self.admin.commit()
        sql=(Path(__file__).resolve().parents[1]/'db/init/540_video_schedule_rows.sql').read_text()
        self.cur.execute(sql);self.cur.execute(sql);self.admin.commit()
        cards=self.board(dict(mode='online',year=2026,month=10))['shelf']
        self.assertEqual(len(cards),2)
        self.assertTrue(all(c['source_column_key']=='row' for c in cards))
        self.assertEqual({tuple(c['ids']) for c in cards},{(2,),(3,)})
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_shelf_events WHERE action='row_upgrade' AND actor_name='系统升级'")
        self.assertEqual(self.cur.fetchone()['n'],5)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_shelf');self.assertEqual(self.cur.fetchone()['n'],6)
        self.assertEqual(len(self.board()['shelf']),1,'field cards are untouched')

    def test_clear_today_preserves_existing_shelf_and_other_mode(self):
        self.save(); item = self.park()
        self.save(station_id=2,inspector_ids=[3])
        self.cur.execute("INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,source_station_name,source_column_key) VALUES('online','2026-10-20','[3]','视频人员','金朝','row')")
        self.admin.commit()
        board = self.board()
        response = self.dispatch('clear_today',board_token=board['board_token'])
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['cleared_count'],6)
        self.assertEqual(response.json['discarded_count'],0)
        self.assertEqual(response.json['parked_count'],1)
        cards=response.json['board']['shelf']
        self.assertEqual(len(cards),2)
        self.assertEqual(cards[0],item)
        self.assertEqual(cards[1]['ids'],[3])
        self.assertEqual(cards[1]['source_station_id'],2)
        self.assertEqual(len(self.board(dict(mode='online',year=2026,month=10))['shelf']),1)
        self.cur.execute('SELECT status FROM inspection_schedule_shelf WHERE id=%s',(item['id'],))
        self.assertEqual(self.cur.fetchone()['status'],'waiting')
        self.cur.execute("SELECT actor_id,action FROM inspection_schedule_shelf_events ORDER BY id DESC LIMIT 1")
        self.assertEqual(dict(self.cur.fetchone()),dict(actor_id=2,action='cleared_to_shelf'))
        again=self.dispatch('clear_today',board_token=response.json['board']['board_token'])
        self.assertEqual(again.status_code,200,again.json)
        self.assertEqual(again.json['parked_count'],0)
        self.assertEqual(again.json['board']['shelf'],cards)

    def test_concurrent_clears_park_each_station_only_once(self):
        self.save();self.save(station_id=2)
        token=self.board()['board_token']
        def clear(_):
            return self.client.application.test_client().post('/api/inspection-schedule/dispatch',json={
                **self.query,'action':'clear_today','board_token':token}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(clear,range(2))),[200,409])
        self.assertEqual(len(self.board()['shelf']),2)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_shelf_events WHERE action='cleared_to_shelf'")
        self.assertEqual(self.cur.fetchone()['n'],2)
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],0)

    def test_expiration_is_audited_nonblocking_and_cannot_place_old_or_future_cards(self):
        self.save(); item = self.park()
        self.cur.execute("UPDATE inspection_schedule_shelf SET scheduled_date='2026-10-19' WHERE id=%s",(item['id'],))
        self.cur.execute("INSERT INTO inspection_schedule_shelf(mode,scheduled_date,inspector_ids,name,source_station_name,source_column_key) VALUES('online','2026-10-21','[3]','旧未来待选','金朝','row')")
        self.admin.commit()
        blocker = self.connect(); lock = blocker.cursor()
        try:
            lock.execute('SELECT pg_advisory_xact_lock(9801,1)')
            self.assertEqual(self.board()['shelf'],[],'old cards hidden even while cleanup cannot acquire lock')
            self.cur.execute('SELECT status FROM inspection_schedule_shelf WHERE id=%s',(item['id'],))
            self.assertEqual(self.cur.fetchone()['status'],'waiting')
        finally:
            blocker.rollback(); lock.close(); blocker.close()
        self.assertEqual(self.board()['shelf'],[])
        self.cur.execute("SELECT actor_id,actor_name FROM inspection_schedule_shelf_events WHERE action='expired'")
        self.assertEqual([dict(r) for r in self.cur.fetchall()],[dict(actor_id=None,actor_name='系统自动清理')]*2)
        self.assertEqual(self.place(item).status_code,409)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_shelf')
        self.assertEqual(self.cur.fetchone()['n'],2,'history is archived, not deleted')

    def test_future_plan_cannot_be_parked_and_clear_rejects_new_shelf_revision(self):
        self.save()
        self.cur.execute("UPDATE inspection_schedule_cells SET scheduled_date='2026-10-21'")
        self.admin.commit()
        self.assertEqual(self.dispatch('park',cells=self.row_cells(1,1)).status_code,409)
        self.cur.execute("UPDATE inspection_schedule_cells SET scheduled_date='2026-10-20'")
        self.admin.commit()
        item = self.park()
        board = self.board()
        self.cur.execute('UPDATE inspection_schedule_shelf SET revision=revision+1 WHERE id=%s',(item['id'],))
        self.admin.commit()
        self.assertEqual(self.dispatch('clear_today',board_token=board['board_token']).status_code,409)
        self.assertEqual(len(self.board()['shelf']),1)

    def test_clear_shelf_audit_failure_rolls_back_cells_tasks_and_cards(self):
        self.save(); self.save(station_id=2); item = self.park()
        board = self.board()
        self.cur.execute("ALTER TABLE inspection_schedule_shelf_events ADD CHECK(action<>'cleared_to_shelf') NOT VALID")
        self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.dispatch('clear_today',board_token=board['board_token']).status_code,500)
        self.assertEqual(self.board()['shelf'],[item])
        row = next(r for r in self.board()['rows'] if r['station_id']==2)
        self.assertTrue(all(c['status']=='assigned' for c in row['cells'].values()))
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],6)

    def test_highlight_identity_comes_from_authenticated_actor_not_query(self):
        self.assertEqual(self.client.get('/api/inspection-schedule',query_string={**self.query,'user_id':1}).json['current_user_id'],2)
        self.assertEqual(self.client.get('/api/staff-availability?user_id=1').json['current_user_id'],2)
        self.save()
        response = self.dispatch('park',cells=self.row_cells(1,1),user_id=1)
        self.assertEqual(response.json['board']['current_user_id'],2)

    def test_concurrent_video_row_placements_only_one_target_wins(self):
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        self.video()
        query=dict(mode='online',year=2026,month=10)
        parked=self.dispatch('park',query,cells=self.video_cells(1,1))
        self.assertEqual(parked.status_code,200,parked.json)
        card=parked.json['board']['shelf'][0]
        def place(sid):
            return self.client.application.test_client().post('/api/inspection-schedule/dispatch',json={
                **query,'action':'place','shelf_id':card['id'],'revision':card['revision'],'cells':self.video_cells(sid)}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(place,[2,5])),[200,409])
        self.cur.execute("SELECT COUNT(*) AS n FROM inspection_schedule_tasks WHERE mode='online' AND status='pending'")
        self.assertEqual(self.cur.fetchone()['n'],3)


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class ShelfTeamDatabaseTests(unittest.TestCase):
    setUp = team_tests.DailyTeamDatabaseTests.setUp
    setUp_base = staff_tests.StaffDatabaseTests.setUp_base
    connect = staff_tests.StaffDatabaseTests.connect
    tearDown = staff_tests.StaffDatabaseTests.tearDown
    availability = staff_tests.StaffDatabaseTests.availability
    post = team_tests.DailyTeamDatabaseTests.post
    confirm = team_tests.DailyTeamDatabaseTests.confirm
    row_cells = dispatch_tests.DispatchDatabaseTests.row_cells
    board = staff_tests.StaffDatabaseTests.board
    dispatch = ShelfDatabaseTests.dispatch

    def test_field_group_edit_also_versions_waiting_cards_and_rejects_old_drop(self):
        self.confirm()
        options = dict(day='2026-10-19')
        preview = self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',**options)).json
        response = self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',**options,token=preview['token']))
        self.assertEqual(response.status_code,200,response.json)
        groups = [g for g in preview['groups'] if g['mode']=='offline']
        source = groups[0]
        student = next(p for p in source['team_members'] if p['position']=='大学生')
        target = next(g for g in groups if g['person']['id'] != source['person']['id'])
        row = next(r for r in self.board()['rows'] if r['station_id']==source['station_id'])
        cells = [dict(station_id=row['station_id'],column_key=k,revision=c['revision']) for k,c in row['cells'].items() if c['status']!='completed']
        parked = self.dispatch('park',cells=cells)
        self.assertEqual(parked.status_code,200,parked.json)
        card = next(c for c in parked.json['board']['shelf'] if c['source_station_id']==source['station_id'])
        cleared=self.dispatch('clear_today',board_token=self.board()['board_token'])
        self.assertEqual(cleared.status_code,200,cleared.json)
        moved = self.post('move',student_id=student['id'],leader_id=target['person']['id'],revision=1)
        self.assertEqual(moved.status_code,200,moved.json)
        current = next(c for c in self.board()['shelf'] if c['id']==card['id'])
        self.assertEqual(current['revision'],card['revision']+1)
        self.assertNotIn(student['id'],current['ids'])
        latest_row = next(r for r in self.board()['rows'] if r['station_id']==source['station_id'])
        cells = [dict(station_id=latest_row['station_id'],column_key=k,revision=c['revision']) for k,c in latest_row['cells'].items() if c['status']!='completed']
        self.assertEqual(self.dispatch('place',shelf_id=card['id'],revision=card['revision'],cells=cells).status_code,409)
        self.assertEqual(self.dispatch('place',shelf_id=current['id'],revision=current['revision'],cells=cells).status_code,200)
