"""Execution invariants in isolated PostgreSQL schemas; no production writes."""
import os
import unittest
from datetime import date
from unittest.mock import patch
from schedule_row_state import today_assignments
from tests import test_schedule_shelf as shelf


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class ExecutionTests(unittest.TestCase):
    setUp=shelf.ShelfDatabaseTests.setUp
    setUp_base=shelf.ShelfDatabaseTests.setUp_base
    connect=shelf.ShelfDatabaseTests.connect
    tearDown=shelf.ShelfDatabaseTests.tearDown
    save=shelf.ShelfDatabaseTests.save
    board=shelf.ShelfDatabaseTests.board
    record=shelf.ShelfDatabaseTests.record
    dispatch=shelf.ShelfDatabaseTests.dispatch
    row_cells=shelf.ShelfDatabaseTests.row_cells
    video=shelf.ShelfDatabaseTests.video
    video_cells=shelf.ShelfDatabaseTests.video_cells

    def annual_save(self,sid=1):
        board=self.board(dict(mode='annual',year=2026))
        row=next(r for r in board['rows'] if r['station_id']==sid)
        return self.client.put('/api/inspection-schedule',json=dict(mode='annual',year=2026,
            scheduled_date='2026-10-20',inspector_ids=[2],cells=[dict(station_id=sid,column_key=k,revision=c['revision'])
                for k,c in row['cells'].items() if c['status']=='unassigned']))

    def test_any_completed_item_locks_whole_field_row_and_clear_leaves_it_alone(self):
        self.save();self.save(station_id=2)
        old=self.board()
        self.record(inspector=2,day='2026-10-20')
        row=self.board()['rows'][0]
        self.assertTrue(row['locked'])
        self.assertTrue(all(c['row_locked'] for c in row['cells'].values()))
        self.assertEqual(self.dispatch('clear_today',board_token=old['board_token']).status_code,409)
        self.assertEqual(self.dispatch('park',cells=self.row_cells(1,1,skip=('odor',))).status_code,409)
        self.assertEqual(self.save(inspector_ids=[],revision=1,cells=self.row_cells(1,1,skip=('odor',))).status_code,409)
        before=row['cells']
        result=self.dispatch('clear_today',board_token=self.board()['board_token'])
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['cleared_station_count'],1)
        self.assertEqual({c['source_station_id'] for c in result.json['board']['shelf']},{2})
        self.assertEqual(result.json['board']['rows'][0]['cells'],before)

    def test_video_started_row_rejects_park_edit_and_replacement_without_consuming_card(self):
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        self.video();self.video(station_id=2,inspector_ids=[3])
        query=dict(mode='online',year=2026,month=10)
        parked=self.dispatch('park',query,cells=self.video_cells(2,1)).json['board']['shelf'][0]
        self.record(table=7,inspector=2,day='2026-10-20')
        edits=self.video_cells(1,1,skip=('safety',))
        self.assertEqual(self.dispatch('park',query,cells=edits).status_code,409)
        self.assertEqual(self.dispatch('place',query,cells=edits,shelf_id=parked['id'],revision=parked['revision']).status_code,409)
        self.assertEqual(self.client.put('/api/inspection-schedule',json=dict(**query,cells=edits,inspector_ids=[],scheduled_date='2026-10-20')).status_code,409)
        self.assertEqual(self.board(query)['shelf'],[parked])
        response=self.dispatch('clear_today',query,board_token=self.board(query)['board_token'])
        self.assertEqual(response.json['cleared_count'],0)
        self.assertTrue(all(c['assignees']==[self.board(query)['rows'][0]['cells']['safety']['assignees'][0]] for c in response.json['board']['rows'][0]['cells'].values()))

    def test_annual_video_only_actual_locks_linked_quarter_and_keeps_every_plan(self):
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1");self.admin.commit()
        self.assertEqual(self.annual_save().status_code,200)
        unstarted=self.board()
        self.cur.execute("SELECT id FROM inspection_tables WHERE table_name='计量稽查检查表（视频）'")
        self.record(table=self.cur.fetchone()['id'],inspector=2,day='2026-10-20')
        self.assertNotEqual(self.board()['board_token'],unstarted['board_token'],'a linked start invalidates the other board token')
        self.assertEqual(self.dispatch('clear_today',board_token=unstarted['board_token']).status_code,409)
        for query in (self.query,dict(mode='annual',year=2026)):
            before=self.board(query)
            self.assertTrue(before['rows'][0]['locked'])
            edits=[dict(station_id=1,column_key=k,revision=c['revision']) for k,c in before['rows'][0]['cells'].items() if c['status']=='assigned']
            self.assertEqual(self.dispatch('park',query,cells=edits).status_code,409)
            response=self.dispatch('clear_today',query,board_token=before['board_token'])
            self.assertEqual(response.json['parked_count'],0)
            self.assertEqual(response.json['board']['rows'][0]['cells'],before['rows'][0]['cells'])

    def test_overdue_is_derived_for_all_modes_keeps_plan_ids_and_actual_wins(self):
        self.assertEqual(self.annual_save().status_code,200)
        self.cur.execute('DELETE FROM staff_daily_teams');self.admin.commit()
        self.assertEqual(self.video(station_id=2,inspector_ids=[3]).status_code,200)
        self.record(table=1,inspector=2,day='2026-10-20')
        with patch('inspection_schedule.today',return_value=date(2026,10,21)):
            for query in (self.query,dict(mode='annual',year=2026),dict(mode='online',year=2026,month=10)):
                board=self.board(query)
                assigned=[c for r in board['rows'] for c in r['cells'].values() if c['status']=='assigned']
                self.assertTrue(assigned)
                self.assertTrue(all(c['overdue'] and c['assignees'] and c['scheduled_date']=='2026-10-20' for c in assigned))
                self.assertTrue(all(not c['overdue'] for r in board['rows'] for c in r['cells'].values() if c['status']=='completed'))
        self.assertTrue(all(not c['overdue'] for r in self.board()['rows'] for c in r['cells'].values()))

    def test_independent_annual_plan_does_not_fill_an_already_started_quarter(self):
        self.record(table=1,day='2026-10-20')
        self.assertEqual(self.annual_save().status_code,200)
        quarter=self.board()['rows'][0]
        self.assertTrue(quarter['locked'])
        self.assertTrue(all(not c['assignees'] for c in quarter['cells'].values()))
        self.assertEqual(self.board(dict(mode='annual',year=2026))['rows'][0]['cells']['metering_site']['status'],'assigned')

    def test_metering_progress_counts_either_applicable_column_once_and_keeps_periods_distinct(self):
        self.cur.execute("UPDATE stations SET monitoring_status='未运行' WHERE id=1")
        self.cur.execute("SELECT id,table_name FROM inspection_tables WHERE table_name LIKE '计量稽查%'")
        tables={r['table_name']:r['id'] for r in self.cur.fetchall()};self.admin.commit()
        self.record(table=tables['计量稽查检查表（视频）'],day='2026-10-02')
        self.record(table=tables['计量稽查检查表（现场）'],day='2026-10-03')
        self.record(station=3,table=tables['计量稽查检查表（现场）'],day='2026-09-03')
        self.record(station=2,table=tables['计量稽查检查表（视频）'],day='2026-10-04')
        result=self.client.get('/api/inspection-schedule/metering-plan?year=2026&month=10').json
        songjin=next(r for r in result['regions'] if r['region']=='松金')
        self.assertEqual((songjin['completed'],songjin['annual_completed'],songjin['total']),(1,2,2))
        pudong=next(r for r in result['regions'] if r['region']=='浦东')
        self.assertEqual((pudong['completed'],pudong['annual_completed']),(0,0),'running-monitor video is not applicable')

    def test_saved_today_projection_merges_linked_boards_preserves_completed_items_and_hides_other_days(self):
        self.annual_save();self.save(station_id=2)
        self.record(inspector=2,day='2026-10-20')
        boards=[self.board(),self.board(dict(mode='annual',year=2026))]
        groups=today_assignments(boards,date(2026,10,20))
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]['stations']),2)
        self.assertEqual(groups[0]['completed'],1)
        self.assertEqual(groups[0]['total'],13)
        self.assertEqual(groups[0]['name'],'外勤步雪琼组')
        self.assertEqual(today_assignments(boards,date(2026,10,21)),[])

    def test_confirm_and_new_preview_both_expose_saved_today_assignments(self):
        preview=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-20'))
        self.assertEqual(preview.status_code,200,preview.json)
        self.assertEqual(preview.json['current_assignments'],[])
        confirmed=self.client.post('/api/inspection-schedule/auto',json=dict(action='confirm',day='2026-10-20',token=preview.json['token']))
        self.assertEqual(confirmed.status_code,200,confirmed.json)
        self.assertTrue(confirmed.json['current_assignments'])
        again=self.client.post('/api/inspection-schedule/auto',json=dict(action='preview',day='2026-10-20'))
        self.assertEqual(again.status_code,200,again.json)
        self.assertEqual(again.json['current_assignments'],confirmed.json['current_assignments'])
        self.assertEqual(again.json['groups'],[])
