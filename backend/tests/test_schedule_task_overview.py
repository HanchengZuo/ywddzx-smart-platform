"""Overview authorization and parity with the self-only inbox."""
import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from flask import Flask, g

from schedule_task_overview import VIEW, register_schedule_task_overview
from tests import test_inspection_schedule as fixture
from tests import test_staff_scheduling as staff_fixture

PATH = "/api/schedule-task-overview"


class OverviewPermissionTests(unittest.TestCase):
    def test_new_permission_is_not_granted_to_existing_roles(self):
        import app as core
        self.assertIn(VIEW, core.PERMISSION_KEYS)
        self.assertNotIn(VIEW, core.PERMISSION_DEPENDENCIES)
        for role in core.ROLE_OPTIONS:
            self.assertEqual(core.role_default_permission(role, VIEW), role == "root")

    def test_both_routes_require_the_independent_permission_before_reading(self):
        app = Flask(__name__)
        connection = MagicMock()
        connect = MagicMock(return_value=connection)
        actor = None
        app.before_request(lambda: setattr(g, "current_user", actor))
        has_permission = MagicMock(return_value=False)
        register_schedule_task_overview(app, connect=connect, has_permission=has_permission)
        client = app.test_client()
        self.assertEqual(client.get(PATH).status_code, 401)
        self.assertEqual(client.get(PATH + "/2").status_code, 401)
        connect.assert_not_called()
        actor = {"id": 17, "role": "supervisor"}
        for path in (PATH + "?user_id=1", PATH + "/2"):
            self.assertEqual(client.get(path).status_code, 403)
        self.assertTrue(all(call.args[1:] == (actor, VIEW) for call in has_permission.call_args_list))
        self.assertEqual(connection.cursor.return_value.execute.call_count, 4)
        self.assertEqual(client.post(PATH + "/2").status_code, 405)


@unittest.skipUnless(os.getenv("INSPECTION_SCHEDULE_DB_TEST") == "1", "isolated database opt-in")
class OverviewDatabaseTests(unittest.TestCase):
    setUp = staff_fixture.StaffDatabaseTests.setUp
    setUp_base = fixture.ScheduleDatabaseTest.setUp
    connect = fixture.ScheduleDatabaseTest.connect
    tearDown = fixture.ScheduleDatabaseTest.tearDown
    save = fixture.ScheduleDatabaseTest.save
    record = fixture.ScheduleDatabaseTest.record

    def initialize(self, day):
        for module in ("schedule_task_overview", "inspection_schedule_tasks"):
            clock = patch(module + ".today", return_value=date.fromisoformat(day))
            clock.start()
            self.addCleanup(clock.stop)
        register_schedule_task_overview(self.client.application, connect=self.connect,
            has_permission=lambda _, actor, key: key in self.permissions)

    def overview(self):
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        return {person["id"]: person for person in response.json["people"]}

    def task_state(self):
        self.cur.execute("SELECT id,status,completion_inspection_id FROM inspection_schedule_tasks ORDER BY id")
        return [dict(row) for row in self.cur.fetchall()]

    def test_partial_progress_is_read_only_and_matches_personal_inbox(self):
        self.initialize("2026-10-20")
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.save(station_id=2).status_code, 200)
        self.record(table=1)
        self.permissions.clear()
        self.assertEqual(self.client.get(PATH).status_code, 403)
        self.permissions.add(VIEW)
        before = self.task_state()
        people = self.overview()
        self.assertEqual(people[3]["buckets"], {})
        counts = people[2]["buckets"]["today_offline"]
        self.assertEqual(counts, dict(total=12, pending=11, completed=1, exempted=0, stations=2))
        response = self.client.get(PATH + "/2?bucket=today_offline&page_size=1&page=999")
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual((response.json["page"], response.json["total_groups"], len(response.json["tasks"])), (2, 2, 6))
        self.assertNotIn("completion_inspection_id", response.json["tasks"][0])
        self.assertEqual(self.task_state(), before)
        own = self.client.get("/api/my-schedule-tasks?user_id=3").json
        self.assertEqual(counts["pending"], own["count"])
        self.assertEqual(counts["completed"], own["buckets"]["today_offline"]["completed"])
        for query in ("page=0", "page_size=51", "bucket=bad"):
            self.assertEqual(self.client.get(PATH + "/2?" + query).status_code, 400)

    def test_historical_visibility_is_partitioned_by_owner(self):
        self.initialize("2026-10-21")
        self.assertEqual(self.save().status_code, 200)
        self.cur.execute("UPDATE inspection_schedule_tasks SET user_id=3 WHERE column_key='finance'")
        self.cur.execute("UPDATE inspection_schedule_tasks SET status='cancelled' WHERE column_key NOT IN ('odor','finance')")
        self.admin.commit()
        self.record(table=1)
        self.permissions.add(VIEW)
        people = self.overview()
        self.assertEqual(people[2]["buckets"], {})
        self.assertEqual(people[3]["buckets"]["history_offline"]["pending"], 1)

    def test_video_waiver_remains_separate_from_completion(self):
        self.initialize("2026-10-20")
        self.cur.execute("DELETE FROM staff_daily_teams")
        self.admin.commit()
        response = self.client.put("/api/inspection-schedule", json=dict(mode="online", year=2026, month=10,
            inspector_ids=[2], scheduled_date="2026-10-20", cells=[dict(station_id=1, column_key=key, revision=0)
            for key in ("safety", "measurement", "service")]))
        self.assertEqual(response.status_code, 200, response.json)
        self.cur.execute("""INSERT INTO inspection_schedule_video_exceptions
            (year,month,station_id,station_name,scheduled_date,reporter_name,reason,task_ids,dispatch_snapshot)
            VALUES(2026,10,1,'沈浦泾南','2026-10-20','测试人员','摄像设备离线','[]','{}')""")
        self.admin.commit()
        self.permissions.add(VIEW)
        count = self.overview()[2]["buckets"]["today_online"]
        self.assertEqual((count["total"], count["pending"], count["completed"], count["exempted"]), (3, 0, 0, 3))
        tasks = self.client.get(PATH + "/2?bucket=today_online").json["tasks"]
        self.assertEqual({task["status"] for task in tasks}, {"exception"})
        self.assertEqual({task["exception_reason"] for task in tasks}, {"摄像设备离线"})
