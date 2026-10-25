"""Driving preparation must never hold a business transaction or dispatch lock."""
import os
import unittest
from unittest.mock import patch

from driving_errors import DrivingUnavailable
from driving_matrix import DrivingService
from tests.test_driving_matrix import seed_ready
from tests import test_staff_daily_teams as teams


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST') == '1', 'isolated PostgreSQL opt-in')
class DrivingDispatchTests(unittest.TestCase):
    setUp_base = teams.DailyTeamDatabaseTests.setUp_base
    tearDown = teams.DailyTeamDatabaseTests.tearDown
    post = teams.DailyTeamDatabaseTests.post
    confirm = teams.DailyTeamDatabaseTests.confirm
    availability = teams.DailyTeamDatabaseTests.availability
    record = teams.DailyTeamDatabaseTests.record
    save = teams.DailyTeamDatabaseTests.save

    def connect(self):
        conn = teams.DailyTeamDatabaseTests.connect(self)
        self.connections.append(conn)
        return conn

    def setUp(self):
        self.connections = []
        teams.DailyTeamDatabaseTests.setUp(self)
        self.confirm()
        self.cur.execute('UPDATE stations SET longitude=121.1+id*.01')
        self.admin.commit()
        seed_ready(self)
        real = DrivingService(self.connect)
        for name in ('prepare','remember','recall'):
            setattr(self.driving_service,name,getattr(real,name))

    def preview(self, **extra):
        return self.client.post('/api/inspection-schedule/auto', json=dict(action='preview',
            strategy='replace_today', day='2026-10-19', offline_count=2, online_count=3, **extra))

    def apply(self, preview):
        return self.client.post('/api/inspection-schedule/auto', json=dict(action='confirm',
            strategy='replace_today', replace_confirmed=True, day='2026-10-19',
            offline_count=2, online_count=3, token=preview['token']))

    def test_preview_and_confirmation_only_read_published_database_without_http(self):
        with patch('amap_driving.urlopen', side_effect=AssertionError('planning cannot call AMap')):
            preview = self.preview()
            self.assertEqual(preview.status_code, 200, preview.json)
            self.assertEqual(preview.json['driving']['source'], 'database')
            self.assertEqual(preview.json['driving']['api_requests'], 0)
            self.assertTrue(any(g.get('driving_seconds', 0) > 0 for g in preview.json['groups']))
            applied = self.apply(preview.json)
        self.assertEqual(applied.status_code, 200, applied.json)

    def test_permission_denial_and_route_failure_do_not_save_quotas_or_schedule(self):
        self.permissions.discard('edit_inspection_schedule')
        with patch.object(self.driving_service, 'prepare') as prepare:
            self.assertEqual(self.preview().status_code, 403)
            prepare.assert_not_called()
        self.permissions.add('edit_inspection_schedule')
        before = self.client.get('/api/inspection-schedule/quotas').json
        with patch.object(self.driving_service, 'prepare', side_effect=DrivingUnavailable('高德暂不可用')):
            result = self.preview(save_quotas=True, quota_revision=before['revision'])
        self.assertEqual(result.status_code, 503, result.json)
        self.assertEqual(self.client.get('/api/inspection-schedule/quotas').json, before)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_cells')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_changed_coordinates_during_database_planning_conflict_before_any_business_write(self):
        prepare = self.driving_service.prepare
        def change(request):
            result = prepare(request)
            self.cur.execute('UPDATE stations SET longitude=longitude+.1 WHERE id=1')
            self.admin.commit()
            return result
        with patch.object(self.driving_service, 'prepare', side_effect=change):
            response = self.preview()
        self.assertEqual(response.status_code, 409, response.json)
        self.cur.execute('SELECT COUNT(*) AS n FROM inspection_schedule_cells')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_changed_record_after_preview_rejects_without_silent_new_traffic_plan(self):
        preview = self.preview()
        self.assertEqual(preview.status_code, 200, preview.json)
        self.record(station=1, table=1, inspector=2)
        with patch('amap_driving.urlopen', side_effect=AssertionError('no network')):
            response = self.apply(preview.json)
        self.assertEqual(response.status_code, 409, response.json)
