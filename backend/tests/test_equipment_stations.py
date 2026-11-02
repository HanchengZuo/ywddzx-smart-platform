import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import psycopg2
from psycopg2.extras import RealDictCursor
import equipment_report_stations as stations
import equipment_report_settings as settings
from report_ai_memory import (
    begin_report_ai_memory,
    end_report_ai_memory,
    set_report_ai_evidence,
)
from ai_usage import build_ai_usage_meta


def issues():
    return [
        dict(
            issue_id=i,
            station_id=11,
            station_name="测试站",
            management_unit="浦东管理片区",
            description="接地线断裂" if i < 3 else "灯具损坏",
            issue_photo=f"{i}.jpg",
            external_standard_id=9067,
        )
        for i in range(1, 4)
    ]


def answer(ctx):
    groups = [
        dict(name="接地线损坏", issue_ids=[1, 2], representative_issue_id=2),
        dict(name="照明损坏", issue_ids=[3], representative_issue_id=3),
    ]
    return dict(
        generated=True,
        payload=dict(groups=groups),
        usage=build_ai_usage_meta("test", success=True, ai_called=True),
    )


class StationValidationTests(unittest.TestCase):
    def test_station_slides_use_station_categories_even_without_regional_selection(
        self,
    ):
        import tempfile
        from PIL import Image
        from pptx import Presentation
        from equipment_report_presentation import build_equipment_template_presentation

        with tempfile.TemporaryDirectory() as directory:
            Image.new("RGB", (400, 300), "white").save(Path(directory) / "photo.jpg")
            rows = [
                dict(r, phrase="原规范短语", cause="参考原因", issue_photo="photo.jpg")
                for r in issues()
            ]
            report = {
                "month": "2026-10",
                "summary": {"station_count": 1, "total_issue_count": 3},
                "equipment_analysis": {
                    "issues": rows,
                    "high_groups": [],
                    "special_issue_ids": [],
                    "station_groups": [
                        dict(station_id=11, groups=answer(None)["payload"]["groups"])
                    ],
                },
                "region_rows": [
                    dict(
                        unit_name="浦东管理片区",
                        station_count=1,
                        issue_count=3,
                        average_issue_count=3,
                    )
                ],
                "station_ranking": [
                    dict(
                        station_id=11,
                        station_name="测试站",
                        management_unit="浦东管理片区",
                        issue_count=3,
                    )
                ],
            }
            path = Path(directory) / "fixture.pptx"
            build_equipment_template_presentation(report, path, directory)
            prs = Presentation(path)
            pages = [
                s
                for s in prs.slides
                if any(
                    shape.has_text_frame and shape.text == "问题总数：3个"
                    for shape in s.shapes
                )
            ]
            self.assertEqual(len(pages), 1)
            content = "\n".join(s.text for s in pages[0].shapes if s.has_text_frame)
            self.assertIn("接地线损坏", content)
            self.assertIn("照明损坏", content)
            self.assertIn("问题ID：2", content)
            self.assertIn("问题ID：3", content)
            self.assertNotIn("暂无对应选题", content)
            for slide in prs.slides:
                for shape in slide.shapes:
                    self.assertLessEqual(shape.top + shape.height, prs.slide_height + 2)

    def test_complete_partition_including_singleton_and_no_outside_or_duplicate_reference(
        self,
    ):
        rows = issues()
        payload = answer(None)["payload"]
        self.assertEqual(len(stations.validate(payload, rows)), 2)
        self.assertEqual(
            stations.validate(
                {
                    "groups": [
                        {
                            "name": "接地线损坏",
                            "issue_ids": [1],
                            "representative_issue_id": 1,
                        }
                    ]
                },
                rows[:1],
            )[0]["issue_ids"],
            [1],
        )
        for bad in [
            [],
            [dict(name="缺陷", issue_ids=[1, 2], representative_issue_id=1)],
            [dict(name="缺陷", issue_ids=[1, 2, 3, 999], representative_issue_id=1)],
            [dict(name="缺陷", issue_ids=[1, 1, 2, 3], representative_issue_id=1)],
        ]:
            with self.assertRaises(ValueError):
                stations.validate({"groups": bad}, rows)
        rows[1]["issue_photo"] = ""
        with self.assertRaises(ValueError):
            stations.validate(payload, rows)

    def test_cache_identity_is_station_local_order_independent_and_changes_with_evidence(
        self,
    ):
        rows = issues()
        self.assertEqual(
            stations.cache_key(rows), stations.cache_key(list(reversed(rows)))
        )
        changed = [dict(r) for r in rows]
        changed[0]["description"] = "新问题"
        self.assertNotEqual(stations.cache_key(rows), stations.cache_key(changed))


@unittest.skipUnless(
    os.getenv("EQUIPMENT_TEST_DSN"), "explicit isolated database required"
)
class StationDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["EQUIPMENT_TEST_DSN"]
        if "dbname=test_" not in cls.dsn:
            raise RuntimeError("Only isolated test_ databases allowed")
        cls.schema = "equipment_" + uuid.uuid4().hex
        c = psycopg2.connect(cls.dsn)
        c.autocommit = True
        with c.cursor() as q:
            q.execute(f"CREATE SCHEMA {cls.schema}")
        c.close()
        with cls.connect() as c, c.cursor() as q:
            q.execute(
                """CREATE TABLE users(id int PRIMARY KEY); INSERT INTO users VALUES(1);
                CREATE TABLE inspection_report_jobs(task_id text PRIMARY KEY,ai_generation_log jsonb);
                INSERT INTO inspection_report_jobs VALUES('a',NULL),('b',NULL);
                CREATE TABLE inspection_report_ai_memory(cache_key text PRIMARY KEY,operation text,report_type text,issue_ids int[],payload jsonb,model text,source_task_id text,created_at timestamptz DEFAULT now());"""
            )
            spec = importlib.util.spec_from_file_location(
                "migration",
                Path(__file__).parents[1]
                / "migrations/versions/20261102_002_equipment_station.py",
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.op = SimpleNamespace(execute=q.execute)
            module.upgrade()
            module.upgrade()

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
            q.execute(
                "TRUNCATE inspection_report_ai_memory,inspection_report_equipment_settings"
            )
        patcher = patch("ai_routing._loader", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def generate(self, job="a"):
        token = begin_report_ai_memory(self.connect, job, "equipment_facilities")
        try:
            set_report_ai_evidence([dict(id=999)])
            return stations.build(issues(), {}, generate=True)
        finally:
            end_report_ai_memory(token)

    def test_persistent_memory_is_readable_without_ai_and_manual_representative_applies(
        self,
    ):
        with patch.object(stations, "run_ai", side_effect=answer) as ai:
            first = self.generate()
            second = self.generate()
            self.assertEqual(first, second)
            self.assertEqual(ai.call_count, 1)
            key = first[0]["groups"][0]["key"]
            with self.connect() as c, c.cursor() as q:
                result = stations.build(
                    issues(),
                    {
                        "station_overrides": {
                            key: {"name": "人工类别", "representative_issue_id": 1}
                        }
                    },
                    q,
                )
            self.assertEqual(result[0]["groups"][0]["name"], "人工类别")
            self.assertEqual(result[0]["groups"][0]["representative_issue_id"], 1)
            self.assertEqual(ai.call_count, 1)

    def test_concurrent_generation_only_calls_provider_once(self):
        def slow(ctx):
            time.sleep(0.15)
            return answer(ctx)

        with patch.object(stations, "run_ai", side_effect=slow) as ai:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(self.generate, ["a", "b"]))
            self.assertEqual(results[0], results[1])
            self.assertEqual(ai.call_count, 1)

    def test_invalid_output_not_cached(self):
        with patch.object(
            stations,
            "run_ai",
            return_value={
                "generated": True,
                "payload": {"groups": []},
                "usage": build_ai_usage_meta("test", success=True),
            },
        ):
            with self.assertRaises(ValueError):
                self.generate()
        with self.connect() as c, c.cursor() as q:
            q.execute("SELECT count(*) AS n FROM inspection_report_ai_memory")
            self.assertEqual(q.fetchone()["n"], 0)

    def test_phrase_defaults_override_revision_conflict_and_rollback(self):
        catalog = [
            dict(external_standard_id="9067", fields={"检查内容": "其他"}),
            dict(external_standard_id="9000", fields={"检查内容短语": "数据库短语"}),
        ]
        with self.connect() as c, c.cursor() as q:
            self.assertEqual(
                settings.reference(q, catalog)["9067"]["phrase"], "非检查表类问题"
            )
            self.assertEqual(
                settings.reference(q, catalog)["9000"]["phrase"], "数据库短语"
            )
            settings.save(
                q,
                {"phrases": {"9067": "人工短语"}, "station_overrides": {}},
                0,
                {"id": 1, "real_name": "测试人"},
            )
        c = self.connect()
        try:
            q = c.cursor()
            self.assertEqual(
                settings.reference(q, catalog)["9067"]["phrase"], "人工短语"
            )
            with self.assertRaises(ValueError):
                settings.save(q, {}, 0, {"id": 1})
            c.rollback()
            self.assertEqual(settings.load(q)["revision"], 1)
            settings.save(
                q,
                {"phrases": {"9067": "不提交"}, "station_overrides": {}},
                1,
                {"id": 1},
            )
            c.rollback()
            self.assertEqual(
                settings.reference(q, catalog)["9067"]["phrase"], "人工短语"
            )
        finally:
            c.close()

    def test_phrase_endpoint_scope_validation_persistence_and_stale_write(self):
        import app as api
        from contextlib import ExitStack

        catalog = [{"external_standard_id": "9067", "fields": {"检查内容": "其他"}}]
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(api, "get_db_connection", side_effect=self.connect)
            )
            authorize = stack.enter_context(
                patch.object(
                    api,
                    "get_authorized_inspection_report_user",
                    return_value={"id": 1, "real_name": "测试人"},
                )
            )
            stack.enter_context(
                patch.object(
                    api, "fetch_equipment_report_catalog", return_value=catalog
                )
            )
            stack.enter_context(patch.object(api, "save_report_workspace"))
            with api.app.test_request_context(method="GET"):
                value = api.manage_equipment_phrases().json
            self.assertEqual(value["standards"][0]["phrase"], "非检查表类问题")
            payload = dict(
                revision=value["meta"]["revision"],
                data_signature=value["data_signature"],
                phrases={"9067": "人工短语"},
            )
            with api.app.test_request_context(
                method="PUT", json={**payload, "phrases": {"99999": "越界"}}
            ):
                self.assertEqual(api.manage_equipment_phrases()[1], 400)
            with api.app.test_request_context(method="PUT", json=payload):
                self.assertEqual(
                    api.manage_equipment_phrases().json["standards"][0]["phrase"],
                    "人工短语",
                )
            with api.app.test_request_context(method="PUT", json=payload):
                self.assertEqual(api.manage_equipment_phrases()[1], 400)
            authorize.side_effect = PermissionError("无权查看")
            with api.app.test_request_context(method="GET"):
                self.assertEqual(api.manage_equipment_phrases()[1], 403)
        with self.connect() as c, c.cursor() as q:
            self.assertEqual(
                settings.load(q)["settings"]["phrases"]["9067"], "人工短语"
            )

    def test_station_endpoint_rejects_outside_representative_and_persists_valid_choice(
        self,
    ):
        import app as api
        from contextlib import ExitStack

        with patch.object(stations, "run_ai", side_effect=answer):
            groups = self.generate()
        raw = [
            dict(r, id=r["issue_id"], standard_id=9067, region="浦东") for r in issues()
        ]
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(api, "get_db_connection", side_effect=self.connect)
            )
            stack.enter_context(
                patch.object(
                    api, "get_authorized_inspection_report_user", return_value={"id": 1}
                )
            )
            stack.enter_context(
                patch.object(
                    api, "fetch_equipment_report_issue_library", return_value=raw
                )
            )
            stack.enter_context(
                patch.object(
                    api,
                    "fetch_equipment_report_catalog",
                    return_value=[{"external_standard_id": "9067", "fields": {}}],
                )
            )
            stack.enter_context(
                patch.object(
                    api, "get_latest_inspection_report_snapshot", return_value={}
                )
            )
            stack.enter_context(patch.object(api, "save_report_workspace"))
            stack.enter_context(patch.object(api.equipment_analysis, "save_overrides"))
            with api.app.test_request_context(
                method="GET", query_string={"month": "2026-10"}
            ):
                value = api.manage_equipment_analysis().json["analysis"]
            group = value["station_groups"][0]["groups"][0]
            payload = dict(
                month="2026-10",
                revision=value["revision"],
                data_signature=value["data_signature"],
                special_issue_ids=[],
                severe_issue_ids=[],
            )
            with api.app.test_request_context(
                method="PUT",
                json={
                    **payload,
                    "station_overrides": {
                        group["key"]: {"name": "编辑", "representative_issue_id": 3}
                    },
                },
            ):
                self.assertEqual(api.manage_equipment_analysis()[1], 400)
            with api.app.test_request_context(
                method="PUT",
                json={
                    **payload,
                    "station_overrides": {
                        group["key"]: {"name": "人工类别", "representative_issue_id": 1}
                    },
                },
            ):
                result = api.manage_equipment_analysis().json["analysis"][
                    "station_groups"
                ][0]["groups"][0]
                self.assertEqual(
                    (result["name"], result["representative_issue_id"]), ("人工类别", 1)
                )
