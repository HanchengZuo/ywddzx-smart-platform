import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from flask import Flask, g
import psycopg2
from psycopg2.extras import RealDictCursor

from inspection_schedule import register_inspection_schedule, save_cell, VIEW_PERMISSION, EDIT_PERMISSION
from inspection_schedule_dispatch import register_schedule_dispatch
from inspection_schedule_catalog import COLUMNS, roster, roster_position
from scheduling_map import period


class ScheduleTest(unittest.TestCase):
    def test_exact_rosters_and_fixed_columns(self):
        offline, online = roster('offline'), roster('online')
        self.assertEqual((len(offline), len(online)), (155, 155))
        self.assertEqual(online, offline)
        self.assertEqual(list(offline)[:3], [('松金', '沈浦泾南'), ('松金', '金朝'), ('松金', '金发')])
        self.assertEqual(offline[('宝静', '闸北第一')], 155)
        self.assertEqual(online[('宝静', '闸北第一')], 155)
        self.assertEqual(offline[('浦东', '爱使浦南')], 24)
        self.assertEqual(online[('浦东', '爱使浦南')], 24)
        self.assertIn(('松金', '泗砖'), offline)
        self.assertEqual(online[('松金', '泗砖')], online[('松金', '三新')]+1)
        self.assertIn(('中油申能', '川朴路'), online)
        self.assertIn(('宝静', '晟隆'), online)
        self.assertEqual([item[1] for item in COLUMNS['offline']], ['无异味', '财务', '设备', '质量健康安全', '非油', '加油现场'])
        self.assertEqual([item[1] for item in COLUMNS['online']], ['安全', '计量', '现场'])
        self.assertFalse(any('计量' in item[2] for item in COLUMNS['offline']))
        self.assertEqual(roster_position({'region': '浦东管理片区', 'station_name': '国郃'}, 'offline'), 26)
        self.assertIsNone(roster_position({'region': '中油浦东', 'station_name': '国郃'}, 'offline'))

    def test_default_permissions_and_retired_routes(self):
        import app as core
        for role in core.ROLE_OPTIONS:
            self.assertEqual(core.role_default_permission(role, VIEW_PERMISSION), role == 'root')
            self.assertEqual(core.role_default_permission(role, EDIT_PERMISSION), role == 'root')
        self.assertEqual(core.PERMISSION_DEPENDENCIES[EDIT_PERMISSION], VIEW_PERMISSION)
        self.assertEqual({item['key'] for item in core.PERMISSION_CATALOG if item['category'] == '巡检排班'},
                         {VIEW_PERMISSION, EDIT_PERMISSION})
        self.assertFalse(any('/api/inspection-plan-' in rule.rule for rule in core.app.url_map.iter_rules()))
        self.assertFalse(hasattr(core, 'mark_related_plan_items_completed'))

    def test_unauthenticated_does_not_connect_and_failure_is_redacted(self):
        app = Flask(__name__)
        connect = MagicMock()
        actor = None
        app.before_request(lambda: setattr(g, 'current_user', actor))
        register_inspection_schedule(app, connect=connect, has_permission=lambda *_: True)
        client = app.test_client()
        self.assertEqual(client.get('/api/inspection-schedule?user_id=1').status_code, 401)
        connect.assert_not_called()
        actor = {'id': 8}
        connect.side_effect = RuntimeError('private connection information')
        with self.assertLogs(level='ERROR'):
            response = client.get('/api/inspection-schedule')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private connection', response.get_data(as_text=True))


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated database opt-in')
class ScheduleDatabaseTest(unittest.TestCase):
    def setUp(self):
        import app as core
        self.config = core.get_db_config()
        if not self.config['dbname'].startswith('test_schedule_'):
            raise RuntimeError('Refusing non-test database')
        for module in ('schedule_common', 'schedule_period', 'annual_metering_plan', 'staff_availability', 'staff_daily_team_http', 'inspection_schedule', 'inspection_schedule_tasks', 'schedule_automation', 'inspection_schedule_dispatch', 'schedule_shelf_store', 'schedule_smart', 'schedule_batch'):
            clock = patch(module + '.today', return_value=date(2026, 10, 19)); clock.start(); self.addCleanup(clock.stop)
        clock = patch('schedule_common.shanghai_now',return_value=datetime(2026,10,19,18,tzinfo=ZoneInfo('Asia/Shanghai')))
        clock.start(); self.addCleanup(clock.stop)
        self.schema = 'schedule_' + uuid.uuid4().hex
        self.admin = psycopg2.connect(**self.config, cursor_factory=RealDictCursor)
        self.cur = self.admin.cursor()
        self.cur.execute(f'CREATE SCHEMA {self.schema}; SET search_path TO {self.schema}')
        self.cur.execute('''CREATE TABLE users(id int PRIMARY KEY,username text,real_name text,role text,account_status text);
          INSERT INTO users VALUES(1,'root','管理','root','active'),(2,'staff','步雪琼','supervisor','active'),
            (3,'lead','孔德辰','supervisor_manager','active'),(4,'finance','财务人员','finance','active');
          CREATE TABLE stations(id int PRIMARY KEY,region text,station_name text,
            include_offline_plan boolean DEFAULT true,include_online_plan boolean DEFAULT true,
            address text,longitude numeric DEFAULT 121.5,latitude numeric DEFAULT 31.2,
            monitoring_status text NOT NULL DEFAULT '运行中');
          INSERT INTO stations(id,region,station_name) VALUES(1,'松金片区','沈浦泾南'),(2,'浦东片区','国郃'),
            (3,'松金片区','泗砖'),(4,'松金片区','新站'),(5,'松金片区','金朝');
          UPDATE stations SET include_offline_plan=false WHERE id=5;
          UPDATE stations SET include_online_plan=false WHERE id=3;
          CREATE TABLE inspection_tables(id serial PRIMARY KEY,table_name text,checklist_mode text,is_active boolean DEFAULT true);
          CREATE TABLE inspections(id serial PRIMARY KEY,station_id int,inspection_table_id int,inspector_id int,inspection_date date,created_at timestamp DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE issues(id serial PRIMARY KEY,inspection_id int,inspector_id int,audit_status text DEFAULT 'pending',created_at timestamp DEFAULT CURRENT_TIMESTAMP);
        ''')
        seen=set()
        for mode in ('offline','online','annual'):
            columns=COLUMNS[mode]
            for _, _, name in columns:
                if name in seen: continue
                seen.add(name)
                actual_mode='online' if name.endswith('（视频）') else 'offline'
                self.cur.execute('INSERT INTO inspection_tables(table_name,checklist_mode) VALUES(%s,%s)', (name, actual_mode))
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/515_inspection_schedule.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/520_staff_scheduling.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/525_staff_daily_teams.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/530_schedule_dispatch.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/535_schedule_shelf.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/540_video_schedule_rows.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/545_staff_dispatch_history.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/550_staff_default_availability.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/555_user_driving_permits.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/560_annual_metering_schedule.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/565_schedule_dispatch_quotas.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/570_video_task_exceptions.sql').read_text())
        self.cur.execute((Path(__file__).resolve().parents[1] / 'db/init/580_driving_matrix.sql').read_text())
        # Existing scheduling scenarios explicitly qualify their leaders, not the migration default.
        self.cur.execute("UPDATE users SET has_driving_permit=TRUE WHERE id IN (2,3)")
        self.cur.execute('CREATE TABLE quality_work_calendar AS SELECT * FROM public.quality_work_calendar')
        self.cur.execute("INSERT INTO staff_availability(person_name,day,available,revision,updated_by) VALUES('步雪琼','2026-10-20',true,1,1),('孔德辰','2026-10-20',true,1,1)")
        self.cur.execute('INSERT INTO staff_daily_teams(day,assignments,revision,updated_by) VALUES(%s,%s,1,1)',
          ('2026-10-20', json.dumps([dict(id=uid,display_name=name,position='管理人员',mode='offline',leader_id=uid,group_name=f'外勤{name}组') for uid,name in [(2,'步雪琼'),(3,'孔德辰')]], ensure_ascii=False)))
        self.admin.commit()
        self.actor = dict(id=2, username='staff', real_name='步雪琼', role='supervisor')
        self.permissions = {VIEW_PERMISSION, EDIT_PERMISSION}
        app = Flask(__name__)
        app.before_request(lambda: setattr(g, 'current_user', self.actor))
        register_inspection_schedule(app, connect=self.connect,
            has_permission=lambda _, actor, key: key in self.permissions)
        register_schedule_dispatch(app, connect=self.connect,
            has_permission=lambda _, actor, key: key in self.permissions)
        self.client = app.test_client()
        self.query = dict(mode='offline', year=2026, quarter=4)

    def connect(self):
        return psycopg2.connect(**self.config, cursor_factory=RealDictCursor,
                                options=f'-c search_path={self.schema} -c timezone=Asia/Shanghai')

    def tearDown(self):
        self.admin.rollback()
        self.cur.execute(f'DROP SCHEMA {self.schema} CASCADE')
        self.admin.commit()
        self.cur.close(); self.admin.close()

    def board(self, query=None):
        response = self.client.get('/api/inspection-schedule', query_string=query or self.query)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        return response.json

    def save(self, **overrides):
        data = {**self.query, 'station_id': 1, 'column_key': 'odor', 'inspector_ids': [2],
                'scheduled_date':'2026-10-20', 'revision': 0, 'user_id': 1, **overrides}
        if data['mode']=='offline' and 'cells' not in data and isinstance(data['column_key'], str) and data['column_key'] in {c[0] for c in COLUMNS['offline']}:
            # Current UI dispatches a whole row, not the retired arbitrary multi-person cell.
            data['cells'] = [dict(station_id=data['station_id'],column_key=key,revision=data['revision']) for key,_,_ in COLUMNS['offline']]
        return self.client.put('/api/inspection-schedule', json=data)

    def record(self, station=1, table=1, inspector=3, day='2026-10-01'):
        self.cur.execute('INSERT INTO inspections(station_id,inspection_table_id,inspector_id,inspection_date) VALUES(%s,%s,%s,%s) RETURNING id', (station, table, inspector, day))
        row = self.cur.fetchone()['id']; self.admin.commit(); return row

    def test_view_edit_denials_and_server_identity(self):
        self.permissions.clear()
        self.assertEqual(self.client.get('/api/inspection-schedule?user_id=1').status_code, 403)
        self.assertEqual(self.save().status_code, 403)
        self.permissions.add(VIEW_PERMISSION)
        self.assertFalse(self.board()['can_edit'])
        self.assertEqual(self.save().status_code, 403)
        self.permissions.add(EDIT_PERMISSION)
        self.assertEqual(self.save().status_code, 200)
        self.cur.execute('SELECT actor_id,before_ids,after_ids FROM inspection_schedule_events')
        event = self.cur.fetchone()
        self.assertEqual(event, dict(actor_id=2, before_ids=[], after_ids=[2]))

    def test_save_multi_person_clear_revision_and_rollback_on_audit_failure(self):
        self.assertEqual(self.save().json['revision'], 1)
        cell = self.board()['rows'][0]['cells']['odor']
        self.assertEqual(cell['status'], 'assigned')
        self.assertEqual({p['id'] for p in cell['assignees']}, {2})
        self.assertEqual(cell['updated_by_name'], '步雪琼')
        self.assertEqual(self.save(revision=1, inspector_ids=[]).json['revision'], 2)
        self.assertEqual(self.board()['rows'][0]['cells']['odor']['status'], 'unassigned')
        self.assertEqual(self.save(revision=0).status_code, 409)
        self.cur.execute('ALTER TABLE inspection_schedule_events ADD CHECK(false) NOT VALID')
        self.admin.commit()
        with self.assertLogs(level='ERROR'):
            self.assertEqual(self.save(revision=2).status_code, 500)
        self.cur.execute('SELECT revision,inspector_ids FROM inspection_schedule_cells')
        self.assertEqual(self.cur.fetchone(), dict(revision=2, inspector_ids=[]))

    def test_actual_records_win_including_zero_issues_unaudited_and_rejected(self):
        self.assertEqual(self.save(inspector_ids=[2]).status_code, 200)
        record = self.record()
        self.cur.execute("INSERT INTO issues(inspection_id,inspector_id,audit_status) VALUES(%s,2,'pending'),(%s,4,'rejected')", (record, record))
        self.admin.commit()
        cell = self.board()['rows'][0]['cells']['odor']
        self.assertEqual(cell['status'], 'completed')
        self.assertEqual(cell['record_count'], 1)
        self.assertEqual({p['id'] for p in cell['completed_inspectors']}, {2,3,4})
        self.assertEqual(self.save(revision=1).status_code, 409)
        self.record(station=2)
        self.assertEqual(self.board()['summary']['completed'], 2)
        self.cur.execute('DELETE FROM issues; DELETE FROM inspections WHERE station_id=1'); self.admin.commit()
        self.assertEqual(self.board()['rows'][0]['cells']['odor']['status'], 'assigned')

    def test_period_edges_and_independent_enrollment_and_rosters(self):
        self.record(day='2026-09-30'); self.record(day='2027-01-01')
        self.assertEqual(self.board()['summary']['completed'], 0)
        self.record(day='2026-12-31')
        self.assertEqual(self.board()['summary']['completed'], 1)
        self.assertEqual([row['station_id'] for row in self.board()['rows']], [1,3,2])
        online = self.board(dict(mode='online', year=2026, month=10))
        self.assertEqual([row['station_id'] for row in online['rows']], [1,5,2])
        self.assertEqual(online['summary']['completed'], 0)
        self.record(table=7, day='2026-10-31')
        self.record(table=7, day='2026-11-01')
        self.assertEqual(self.board(dict(mode='online', year=2026, month=10))['summary']['completed'], 1)
        self.assertEqual(self.board(dict(mode='online', year=2026, month=11))['summary']['completed'], 1)

    def test_video_enrollment_is_authoritative_and_sizhuan_follows_sanxin_without_number_gaps(self):
        query=dict(mode='online',year=2026,month=10)
        self.cur.execute('''INSERT INTO stations(id,region,station_name,include_online_plan) VALUES
          (6,'松金片区','三新',true),(7,'松金片区','松江第二',true),
          (8,'松金片区','松江第三',true),(9,'松金片区','松江第一',true),
          (10,'松金片区','望榭',false),(11,'松金片区','欣宝',true),
          (12,'松金片区','叶新',true);
          UPDATE stations SET include_online_plan=true WHERE id=3;''')
        self.admin.commit()
        board=self.board(query)
        names=[r['station_name'] for r in board['rows']]
        self.assertEqual(names[names.index('三新')+1],'泗砖')
        self.assertEqual(names[names.index('松江第一')+1],'欣宝')
        self.assertNotIn('望榭',names)
        self.assertEqual([r['sequence'] for r in board['rows']],list(range(1,len(board['rows'])+1)))
        self.assertEqual(board['roster_total'],155)
        self.assertNotIn('泗砖',[s['station_name'] for s in board['excluded_stations']])
        # A previously hard-excluded station supports record-derived completion and manual dispatch.
        row=next(r for r in self.board(query)['rows'] if r['station_id']==3)
        self.assertEqual(row['cells']['safety']['status'],'unassigned')
        self.cur.execute("DELETE FROM staff_daily_teams WHERE day='2026-10-20'");self.admin.commit()
        result=self.client.put('/api/inspection-schedule',json=dict(**query,inspector_ids=[2],scheduled_date='2026-10-20',
            cells=[dict(station_id=3,column_key=key,revision=cell['revision']) for key,cell in row['cells'].items() if cell['status']!='completed']))
        self.assertEqual(result.status_code,200,result.json)
        self.record(station=3,table=7)
        self.cur.execute('UPDATE stations SET include_online_plan=false WHERE id=3');self.admin.commit()
        hidden=self.board(query)
        self.assertNotIn(3,[r['station_id'] for r in hidden['rows']])
        self.assertEqual([r['sequence'] for r in hidden['rows']],list(range(1,len(hidden['rows'])+1)))
        self.cur.execute('UPDATE stations SET include_online_plan=true WHERE id=3');self.admin.commit()
        restored=next(r for r in self.board(query)['rows'] if r['station_id']==3)
        self.assertEqual(restored['cells']['measurement']['status'],'assigned')
        self.assertEqual(restored['cells']['safety']['status'],'completed')

    def test_display_numbers_do_not_change_station_ids_or_canonical_order(self):
        for query in (self.query,dict(mode='annual',year=2026),dict(mode='online',year=2026,month=10)):
            rows=self.board(query)['rows']
            self.assertEqual([r['sequence'] for r in rows],list(range(1,len(rows)+1)))
            self.assertEqual([r['station_id'] for r in rows],sorted([r['station_id'] for r in rows],key=lambda sid:roster_position(next(r for r in rows if r['station_id']==sid),query['mode'])))

    def test_authorized_roles_share_the_full_board_and_can_edit_outside_their_own_region(self):
        for role in ('area_account', 'station_manager', 'quality_safety', 'finance'):
            self.actor = dict(id=4, username='scoped', real_name='授权用户', role=role, station_id=2,
                              inspection_table_scope_ids=[2], station_region_scope_values=['浦东片区'])
            board = self.board()
            self.assertEqual([row['station_id'] for row in board['rows']], [1,3,2])
            self.assertEqual(len([c for c in board['columns'] if c['table_id']]), 6)
        self.assertEqual(self.save(inspector_ids=[2]).status_code, 200)
        self.assertEqual(self.save(station_id=2, column_key='finance', inspector_ids=[2]).status_code, 200)

    def test_station_switches_tables_and_inspector_roles_are_revalidated(self):
        for overrides, status in [({'station_id': 4}, 403), ({'station_id': 5}, 403),
            ({'inspector_ids': [1]},400), ({'inspector_ids': [4]},400), ({'inspector_ids': [999]},400),
            ({'inspector_ids': [True]},400), ({'revision': True},400), ({'column_key':'measurement'},400), ({'column_key':[]},400)]:
            self.assertEqual(self.save(**overrides).status_code, status, overrides)
        self.cur.execute("UPDATE users SET account_status='disabled' WHERE id=2"); self.admin.commit()
        self.assertEqual({p['id'] for p in self.board()['inspectors']}, {3})
        self.assertEqual(self.save().status_code, 400)
        self.cur.execute('UPDATE inspection_tables SET is_active=false WHERE id=1'); self.admin.commit()
        self.assertEqual(self.save().status_code, 409)

    def test_transaction_locks_station_and_same_cell_across_connections(self):
        chosen, start, end = period(self.query)
        conn = self.connect(); other = self.connect()
        try:
            with conn.cursor() as cur:
                save_cell(cur, self.actor, dict(station_id=1,column_key='odor',inspector_ids=[2],scheduled_date='2026-10-20',revision=0), chosen,start,end)
            with other.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    cur.execute('UPDATE stations SET include_offline_plan=false WHERE id=1')
                other.rollback()
                cur.execute("SET LOCAL lock_timeout='100ms'")
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    save_cell(cur, self.actor, dict(station_id=1,column_key='odor',inspector_ids=[3],scheduled_date='2026-10-20',revision=0), chosen,start,end)
                other.rollback(); conn.commit()
            self.assertEqual(self.save(inspector_ids=[3]).status_code, 409)
        finally:
            conn.close(); other.close()

    def test_migration_does_not_inherit_retired_grants_or_reset_new_grants(self):
        self.cur.execute('''CREATE TABLE user_permissions(permission_key text); CREATE TABLE role_permissions(permission_key text);
          INSERT INTO user_permissions VALUES('view_inspection_plans'),('edit_inspection_schedule');
          INSERT INTO role_permissions VALUES('manage_inspection_plans'),('unrelated');''')
        inspection = self.record()
        self.cur.execute('CREATE TABLE inspection_plan_station_items(completed_inspection_id int REFERENCES inspections(id))')
        self.cur.execute('INSERT INTO inspection_plan_station_items VALUES(%s)', (inspection,))
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/20261019_002_inspection_schedule.py'
        spec = importlib.util.spec_from_file_location('schedule_migration', path)
        migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
        with patch.object(migration.op, 'execute', side_effect=self.cur.execute):
            migration.upgrade(); migration.upgrade()
        self.cur.execute('SELECT permission_key FROM user_permissions')
        self.assertEqual(self.cur.fetchall(), [dict(permission_key='edit_inspection_schedule')])
        self.cur.execute('SELECT permission_key FROM role_permissions')
        self.assertEqual(self.cur.fetchall(), [dict(permission_key='unrelated')])
        self.cur.execute('DELETE FROM inspections WHERE id=%s', (inspection,))
        self.cur.execute('SELECT completed_inspection_id FROM inspection_plan_station_items')
        self.assertIsNone(self.cur.fetchone()['completed_inspection_id'])
