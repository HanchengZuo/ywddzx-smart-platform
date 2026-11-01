import importlib.util
import io
import os
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from flask import Flask, g, request
from PIL import Image
import psycopg2
from psycopg2.extras import RealDictCursor
from certificates import register_certificates, scope, unread_count

TYPES = [
    dict(
        code="permit",
        name="测试许可证",
        recommended_reminder_days=30,
        legal_reminder_days=7,
        rule="既有测试提醒规则",
    )
]
TODAY = datetime.now(ZoneInfo("Asia/Shanghai")).date()


class ScopeTests(unittest.TestCase):
    def test_role_defaults_cannot_be_revoked_and_global_grants_are_independent(self):
        self.assertEqual(
            scope(
                {"role": "station_manager", "station_id": 11},
                {"view_all_certificates": False},
                set(),
            )[1],
            [11],
        )
        self.assertEqual(scope({"role": "area_account"}, {}, {"浦东"})[2], "region")
        self.assertEqual(
            scope({"role": "area_account"}, {"view_all_certificates": True}, {"浦东"})[
                2
            ],
            "all",
        )
        self.assertEqual(
            scope(
                {"role": "area_account"},
                {"view_all_certificates": True},
                {"浦东"},
                "register",
            )[2],
            "region",
        )
        self.assertEqual(
            scope({"role": "finance"}, {"register_all_certificates": True}, set())[2],
            "none",
        )
        self.assertEqual(
            scope(
                {"role": "finance"},
                {"register_all_certificates": True},
                set(),
                "register",
            )[2],
            "all",
        )


@unittest.skipUnless(
    os.getenv("CERTIFICATE_TEST_DSN"), "requires explicit isolated PostgreSQL database"
)
class CertificateDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["CERTIFICATE_TEST_DSN"]
        if "dbname=test_" not in cls.dsn:
            raise RuntimeError("Use only an isolated test_ database")
        cls.schema = "certificate_" + uuid.uuid4().hex
        c = psycopg2.connect(cls.dsn)
        c.autocommit = True
        with c.cursor() as q:
            q.execute(f"CREATE SCHEMA {cls.schema}")
        c.close()
        with cls.connect() as c, c.cursor() as q:
            q.execute(
                """CREATE TABLE users(id integer PRIMARY KEY,real_name text,username text);
                INSERT INTO users SELECT i,'测试用户'||i,'user'||i FROM generate_series(1,8) i;
                CREATE TABLE stations(id integer PRIMARY KEY,station_name text,region text);
                INSERT INTO stations VALUES(11,'第一站','浦东'),(22,'第二站','松金'),(33,'第三站','浦东');
                CREATE TABLE system_page_visibility(page_key text PRIMARY KEY,is_visible boolean,updated_by integer);
                INSERT INTO system_page_visibility VALUES('/inspection/certificates',FALSE,1);"""
            )
            q.execute(
                (
                    Path(__file__).parents[1] / "db/init/600_station_certificates.sql"
                ).read_text()
            )
            q.execute(
                "INSERT INTO station_certificates(station_id,certificate_type,certificate_name,expiry_date,updated_by) VALUES(11,'permit','测试许可证',CURRENT_DATE,1)"
            )
            path = (
                Path(__file__).parents[1]
                / "migrations/versions/20261102_001_certificates.py"
            )
            spec = importlib.util.spec_from_file_location("certificate_migration", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.op = SimpleNamespace(execute=q.execute)
            module.upgrade()
            module.upgrade()
            q.execute("SELECT count(*) AS n FROM station_certificate_history")
            assert q.fetchone()["n"] == 1
            q.execute(
                "SELECT count(*) AS n FROM system_page_visibility WHERE page_key LIKE '/certificates/%%' AND NOT is_visible"
            )
            assert q.fetchone()["n"] == 3

    @classmethod
    def connect(cls):
        return psycopg2.connect(
            cls.dsn,
            options=f"-c search_path={cls.schema}",
            cursor_factory=RealDictCursor,
        )

    @classmethod
    def tearDownClass(cls):
        c = psycopg2.connect(cls.dsn)
        c.autocommit = True
        with c.cursor() as q:
            q.execute(f"DROP SCHEMA {cls.schema} CASCADE")
        c.close()

    def setUp(self):
        with self.connect() as c, c.cursor() as q:
            q.execute("TRUNCATE station_certificates RESTART IDENTITY CASCADE")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.users = {
            1: dict(id=1, role="root"),
            2: dict(id=2, role="station_manager", station_id=11),
            3: dict(id=3, role="area_account"),
            4: dict(id=4, role="finance"),
            5: dict(id=5, role="finance"),
            6: dict(id=6, role="finance"),
            7: dict(id=7, role="station_manager", station_id=22),
            8: dict(id=8, role="area_account"),
        }
        self.perms = {
            5: {"view_all_certificates": True},
            6: {"register_all_certificates": True},
            7: {"view_all_certificates": True, "register_all_certificates": True},
            8: {"view_all_certificates": True},
        }
        self.app = Flask(__name__)

        @self.app.before_request
        def identity():
            g.current_user = {
                **self.users[int(request.headers.get("X-User", 1))],
                "real_name": "测试操作人",
            }

        register_certificates(
            self.app,
            connect=self.connect,
            permissions=lambda q, u: self.perms.get(u["id"], {}),
            regions=lambda q, u: {"浦东"} if u["role"] == "area_account" else set(),
            types=TYPES,
            storage_root=self.temp.name,
            file_user=lambda: g.current_user,
        )

    def get(self, url, user=1):
        result = self.app.test_client().get(url, headers={"X-User": str(user)})
        self.addCleanup(result.close)
        return result

    def post(self, url, data, user=1):
        return self.app.test_client().post(
            url, data=data, headers={"X-User": str(user)}
        )

    def register(
        self, user=1, station=11, revision=0, present=True, days=20, photo=True
    ):
        data = dict(
            station_id=str(station),
            revision=str(revision),
            certificate_type="permit",
            is_present=str(present).lower(),
            expiry_date=(TODAY + timedelta(days=days)).isoformat(),
        )
        if photo:
            stream = io.BytesIO()
            Image.new("RGB", (80, 120), "white").save(stream, "PNG")
            stream.seek(0)
            data["photo"] = (stream, "test.png")
        return self.post("/api/station-certificates", data, user)

    def test_scope_for_all_pages_photos_history_and_registration(self):
        first = self.register(station=11).json
        second = self.register(station=22).json
        self.assertEqual(self.get("/api/station-certificates", 2).json["total"], 1)
        self.assertEqual(self.get("/api/station-certificates", 3).json["total"], 1)
        self.assertEqual(self.get("/api/station-certificates", 5).json["total"], 2)
        self.assertEqual(self.get("/api/station-certificates", 4).status_code, 403)
        self.assertEqual(self.get("/api/station-certificates", 6).status_code, 403)
        self.assertEqual(
            len(
                self.get("/api/station-certificates/options?purpose=register", 6).json[
                    "stations"
                ]
            ),
            3,
        )
        self.assertEqual(self.register(user=5, station=33).status_code, 403)
        self.assertEqual(self.register(user=2, station=33).status_code, 403)
        self.assertEqual(self.register(user=3, station=22, revision=1).status_code, 403)
        self.assertEqual(self.register(user=3, station=33).status_code, 200)
        self.assertEqual(self.register(user=7, station=11, revision=1).status_code, 200)
        self.assertEqual(
            self.get(
                f"/api/station-certificates/{second['id']}/history", 2
            ).status_code,
            403,
        )
        url = f"/storage/certificates/{second['id']}/{second['history_id']}.jpg"
        self.assertEqual(self.get(url, 2).status_code, 403)
        allowed = self.get(url, 5)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers["Cache-Control"], "private, no-store")
        allowed.close()
        self.assertEqual(self.get(url, 8).status_code, 200)

    def test_required_photo_absence_and_immutable_history(self):
        missing = self.register(photo=False)
        self.assertEqual(missing.status_code, 400)
        self.assertIn("请上传证照图片", missing.json["error"])
        first = self.register().json
        second = self.register(revision=1, days=100).json
        self.assertEqual(self.register(revision=0).status_code, 409)
        third_result = self.register(revision=2, present=False, photo=False)
        self.assertEqual(third_result.status_code, 200)
        third = third_result.json
        row = self.get("/api/station-certificates").json["records"][0]
        self.assertFalse(row["is_present"])
        self.assertIsNone(row["expiry_date"])
        self.assertEqual(row["status"], "absent")
        self.assertFalse(row["photo_url"])
        history = self.get(f"/api/station-certificates/{third['id']}/history").json[
            "records"
        ]
        self.assertEqual([r["revision"] for r in history], [3, 2, 1])
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.jpg"))), 2)
        self.assertTrue(history[1]["photo_url"])
        self.assertNotEqual(history[1]["photo_url"], history[2]["photo_url"])
        self.assertEqual(
            self.get(
                f"/storage/certificates/{first['id']}/{first['history_id']}.jpg"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.get("/api/station-certificates?mode=reminders").json["total"], 0
        )

    def test_reminder_receipts_are_user_revision_and_phase_specific(self):
        row = self.register().json
        record = self.get("/api/station-certificates", 2).json["records"][0]

        def read(user, rev=1, status="recommended"):
            return self.app.test_client().post(
                f"/api/station-certificates/{row['id']}/read",
                json={"revision": rev, "status": status},
                headers={"X-User": str(user)},
            )

        self.assertTrue(record["unread"])
        self.assertEqual(read(2).status_code, 200)
        self.assertEqual(
            self.get("/api/station-certificates", 2).json["summary"]["unread"], 0
        )
        self.assertEqual(
            self.get("/api/station-certificates", 3).json["summary"]["unread"], 1
        )
        self.assertEqual(read(4).status_code, 403)
        self.register(revision=1, days=5)
        self.assertEqual(read(2).status_code, 409)
        self.assertTrue(
            self.get("/api/station-certificates", 2).json["records"][0]["unread"]
        )
        self.assertEqual(read(2, 2, "legal").status_code, 200)
        with self.connect() as c, c.cursor() as q:
            q.execute(
                "UPDATE station_certificates SET expiry_date=%s WHERE id=%s",
                (TODAY - timedelta(days=1), row["id"]),
            )
        self.assertTrue(
            self.get("/api/station-certificates", 2).json["records"][0]["unread"]
        )

    def test_server_filters_pagination_and_summary(self):
        self.register(station=11, days=-2)
        self.register(station=22, days=100)
        self.register(station=33, days=5)
        r = self.get("/api/station-certificates?page_size=1&page=2").json
        self.assertEqual((r["total"], len(r["records"]), r["page"]), (3, 1, 2))
        self.assertEqual(r["summary"]["due"], 2)
        self.assertEqual(
            self.get("/api/station-certificates?keyword=第三&region=浦东").json[
                "total"
            ],
            1,
        )
        self.assertEqual(
            self.get("/api/station-certificates?mode=reminders").json["total"], 2
        )
        self.assertEqual(
            self.get("/api/station-certificates?region=松金", 2).json["total"], 0
        )

    def test_fake_images_invalid_dates_and_stale_updates_do_not_create_evidence(self):
        data = dict(
            station_id="11",
            certificate_type="permit",
            revision="0",
            is_present="true",
            expiry_date=TODAY.isoformat(),
        )
        invalid = self.post(
            "/api/station-certificates",
            {**data, "photo": (io.BytesIO(b"not an image"), "fake.jpg")},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("有效的证照图片", invalid.json["error"])
        invalid_date = self.post(
            "/api/station-certificates",
            {**data, "start_date": (TODAY + timedelta(days=1)).isoformat()},
        )
        self.assertEqual(invalid_date.status_code, 400)
        self.assertEqual(self.get("/api/station-certificates").json["total"], 0)
        self.assertEqual(list(Path(self.temp.name).rglob("*.jpg")), [])

    def test_claiming_other_identity_in_payload_never_expands_scope_and_delete_is_removed(
        self,
    ):
        self.register(station=22)
        data = dict(
            station_id="22",
            certificate_type="permit",
            revision="1",
            is_present="false",
            user_id="1",
        )
        self.assertEqual(
            self.post("/api/station-certificates", data, user=2).status_code, 403
        )
        self.assertEqual(
            self.get("/api/station-certificates?user_id=1", 2).json["total"], 0
        )
        self.assertEqual(
            self.app.test_client().delete("/api/station-certificates/1").status_code,
            404,
        )

    def test_concurrent_initial_registration_has_one_winner_and_no_orphan_files(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.register(), range(2)))
        self.assertEqual(sorted(r.status_code for r in results), [200, 409])
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.jpg"))), 1)
        with self.connect() as c, c.cursor() as q:
            q.execute("SELECT count(*) AS n FROM station_certificate_history")
            self.assertEqual(q.fetchone()["n"], 1)

    def test_database_failure_rolls_back_new_version_and_removes_only_new_file(self):
        old = self.register().json
        with self.connect() as c, c.cursor() as q:
            q.execute(
                "CREATE FUNCTION fail_certificate_history() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'forced test rollback'; END; $$ LANGUAGE plpgsql; CREATE TRIGGER fail_history BEFORE INSERT ON station_certificate_history FOR EACH ROW EXECUTE FUNCTION fail_certificate_history();"
            )
        try:
            self.assertEqual(self.register(revision=1).status_code, 500)
        finally:
            with self.connect() as c, c.cursor() as q:
                q.execute(
                    "DROP TRIGGER fail_history ON station_certificate_history; DROP FUNCTION fail_certificate_history()"
                )
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.jpg"))), 1)
        history = self.get(f"/api/station-certificates/{old['id']}/history").json[
            "records"
        ]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["revision"], 1)
