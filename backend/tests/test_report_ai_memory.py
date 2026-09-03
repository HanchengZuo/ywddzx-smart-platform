import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from unittest.mock import patch

import psycopg2
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from ai_usage import build_ai_usage_meta
from report_ai_memory import (
    CLASSIFICATION_TABLES, INSIGHT_FIELDS, ReportMemory, ReportMemoryUnavailable,
    begin_report_ai_memory, end_report_ai_memory, fingerprint,
    record_classification_reuse, remember_report_ai, report_ai_generation_log,
    set_report_ai_evidence, valid_classifications, valid_insights,
)


def ai_result(payload):
    return {"generated": True, "payload": payload,
            "usage": build_ai_usage_meta("deepseek-v4-pro", "sample prompt", "sample result",
                                         ai_called=True, success=True)}


def finance_payload():
    return {"result_analysis": [{"title": "分析", "content": "仅服务端保存的分析", "related_issue_ids": [1]}],
            "content_suggestions": [{"title": "建议", "content": "建议内容"}]}


class MemoryUnitTest(unittest.TestCase):
    def test_order_independent_issues_but_ordered_priorities(self):
        self.assertEqual(fingerprint({"issues": [{"issue_id": 2}, {"issue_id": 1}]}),
                         fingerprint({"issues": [{"issue_id": 1}, {"issue_id": 2}]}))
        self.assertNotEqual(fingerprint({"priority": [1, 2]}), fingerprint({"priority": [2, 1]}))

    def test_invalid_partial_and_duplicate_classification_not_remembered(self):
        payload = {"classifications": [{"issue_id": 1, "category": "A"},
                                       {"issue_id": 2, "category": "其他"},
                                       {"issue_id": 3, "category": "A"},
                                       {"issue_id": 3, "category": "B"},
                                       {"issue_id": 999, "category": "A"}]}
        self.assertEqual(set(valid_classifications(ai_result(payload), {1, 2, 3}, ["A", "B"])), {1})

    def test_unrelated_payload_and_out_of_scope_ids_not_cacheable(self):
        self.assertFalse(valid_insights({"message": "error"}, "finance_insights", {1}))
        payload = finance_payload()
        self.assertTrue(valid_insights(payload, "finance_insights", {1}))
        payload["result_analysis"][0]["related_issue_ids"] = [999]
        self.assertFalse(valid_insights(payload, "finance_insights", {1}))

    def test_all_six_insight_schemas_registered(self):
        self.assertEqual(len(INSIGHT_FIELDS), 6)

    def test_no_job_context_preserves_non_report_call_behavior(self):
        called = []
        @remember_report_ai("finance_insights", "system", lambda _: "prompt", "model")
        def direct(context):
            called.append(context)
            return "unchanged"
        self.assertEqual(direct({"id": 1}), "unchanged")
        self.assertEqual(called, [{"id": 1}])

    def test_unavailable_memory_blocks_paid_calls(self):
        def broken():
            raise RuntimeError("database secret")
        with self.assertRaises(ReportMemoryUnavailable) as error:
            begin_report_ai_memory(broken, "task", "finance")
        self.assertNotIn("database secret", str(error.exception))
        self.assertIsNone(report_ai_generation_log())

    def test_quality_trace_draw_stable_for_identical_ids(self):
        from app import build_quality_report_ai_context
        rows = [{"id": 1, "description": "问题一", "station_name": "甲", "region": "浦东"},
                {"id": 2, "description": "问题二", "station_name": "乙", "region": "松金"}]
        first = build_quality_report_ai_context(date(2026, 7, 1), rows, [], {})
        second = build_quality_report_ai_context(date(2026, 7, 1), list(reversed(rows)), [], {})
        self.assertEqual(first["designated_typical_issue_id"], second["designated_typical_issue_id"])

    def test_snapshot_metadata_does_not_replace_historical_log(self):
        from app import attach_report_snapshot_meta, serialize_inspection_report_job
        log = {"events": [{"outcome": "cache_hit"}]}
        self.assertEqual(attach_report_snapshot_meta({"ai_generation_log": log})["ai_generation_log"], log)
        self.assertEqual(serialize_inspection_report_job({"task_id": "x", "ai_generation_log": log})["ai_generation_log"], log)


@unittest.skipUnless(os.environ.get("REPORT_AI_MEMORY_TEST_DSN"), "requires isolated PostgreSQL test DSN")
class MemoryPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["REPORT_AI_MEMORY_TEST_DSN"]
        cls.schema = "ai_memory_test_" + uuid.uuid4().hex
        conn = psycopg2.connect(cls.dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{cls.schema}"')
        conn.close()
        cls.engine = sa.create_engine("postgresql+psycopg2://", creator=cls.connect)
        path = Path(__file__).resolve().parents[1] / "migrations/versions/20260903_001_report_ai_memory.py"
        spec = importlib.util.spec_from_file_location("memory_migration", path)
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)
        with cls.engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE inspection_report_jobs (task_id VARCHAR(64) PRIMARY KEY)"))
            with Operations.context(MigrationContext.configure(connection)):
                cls.migration.upgrade()
            for table in CLASSIFICATION_TABLES.values():
                connection.execute(sa.text(f"""CREATE TABLE {table} (
                    issue_id BIGINT PRIMARY KEY, effective_category TEXT,
                    classification_source TEXT, reason TEXT)"""))

    @classmethod
    def connect(cls):
        return psycopg2.connect(cls.dsn, options=f"-c search_path={cls.schema}")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        conn = psycopg2.connect(cls.dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{cls.schema}" CASCADE')
        conn.close()

    def setUp(self):
        with self.engine.begin() as connection:
            for table in ["inspection_report_jobs", "inspection_report_ai_memory", *CLASSIFICATION_TABLES.values()]:
                connection.execute(sa.text(f"TRUNCATE {table}"))

    def new_job(self, report_type="finance"):
        task = uuid.uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO inspection_report_jobs (task_id) VALUES (:task)"), {"task": task})
        return ReportMemory(self.connect, task, report_type)

    def test_full_analysis_persists_across_jobs_and_reordering_with_zero_cost(self):
        calls = []
        def run(context):
            calls.append(context)
            return ai_result(finance_payload())
        ctx = {"issues": [{"issue_id": 1, "description": "secret issue"}, {"issue_id": 2}]}
        first = self.new_job()
        result = first.batch(run, ctx, "finance_insights", "prompt-v1", "deepseek-v4-pro")
        second = self.new_job()
        ctx["issues"].reverse()
        reused = second.batch(run, ctx, "finance_insights", "prompt-v1", "deepseek-v4-pro")
        self.assertEqual(len(calls), 1)
        self.assertEqual(reused["payload"], result["payload"])
        self.assertFalse(reused["usage"]["ai_called"])
        self.assertEqual(reused["usage"]["total_cost_est"], 0)
        log = second.snapshot()
        self.assertEqual(log["summary"]["ai_calls"], 0)
        self.assertEqual(log["summary"]["reuse_steps"], 1)
        self.assertEqual(log["events"][0]["source_task_id"], first.task_id)
        self.assertNotIn("secret issue", json.dumps(log))
        self.assertNotIn("仅服务端保存的分析", json.dumps(log, ensure_ascii=False))
        with second.connection() as cur:
            cur.execute("SELECT ai_generation_log FROM inspection_report_jobs WHERE task_id=%s", (second.task_id,))
            self.assertEqual(cur.fetchone()["ai_generation_log"], log)

    def test_data_rules_prompt_or_model_changes_trigger_fresh_call(self):
        calls = []
        def run(_):
            calls.append(1)
            return ai_result(finance_payload())
        memory = self.new_job()
        ctx = {"issues": [{"issue_id": 1}]}
        memory.evidence = {"description": "a" * 1000, "priority": [1, 2]}
        memory.batch(run, ctx, "finance_insights", "v1", "model1")
        memory.batch(run, ctx, "finance_insights", "v1", "model1")
        self.assertEqual(len(calls), 1)
        memory.evidence["description"] += "edited after prompt truncation"
        memory.batch(run, ctx, "finance_insights", "v1", "model1")
        memory.evidence["priority"] = [2, 1]
        memory.batch(run, ctx, "finance_insights", "v1", "model1")
        memory.batch(run, ctx, "finance_insights", "v2", "model1")
        memory.batch(run, ctx, "finance_insights", "v2", "model2")
        self.assertEqual(len(calls), 5)

    def test_failed_fallback_or_invalid_results_are_not_cached(self):
        memory = self.new_job()
        ctx = {"issues": [{"issue_id": 1}]}
        failed = {"generated": False, "payload": None,
                  "usage": build_ai_usage_meta("model", ai_called=True, fallback_used=True)}
        for result in [failed, ai_result({"unexpected": []}), ai_result({})]:
            memory.batch(lambda _: result, ctx, "finance_insights", "v1", "model")
        with memory.connection() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM inspection_report_ai_memory")
            self.assertEqual(cur.fetchone()["n"], 0)
        memory.batch(lambda _: ai_result(finance_payload()), ctx, "finance_insights", "v1", "model")
        self.assertTrue(memory.snapshot()["summary"]["fallback_steps"])

    def test_concurrent_same_analysis_only_calls_ai_once(self):
        calls = []
        barrier = threading.Barrier(2)
        def run(_):
            calls.append(1)
            time.sleep(0.35)
            return ai_result(finance_payload())
        def job(_):
            memory = self.new_job()
            barrier.wait()
            memory.batch(run, {"issues": [{"issue_id": 1}]}, "finance_insights", "v1", "model")
            return memory.snapshot()
        with ThreadPoolExecutor(max_workers=2) as pool:
            logs = list(pool.map(job, range(2)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(log["summary"]["reuse_steps"] for log in logs), 1)

    def test_classification_by_id_survives_different_batches_and_manual_override(self):
        batches = []
        def run(ctx):
            batches.append([item["issue_id"] for item in ctx["issues"]])
            return ai_result({"classifications": [{"issue_id": item["issue_id"], "category": "A"} for item in ctx["issues"]]})
        first = self.new_job("non_oil")
        first.classifications(run, {"issues": [{"issue_id": 1}, {"issue_id": 2}], "allowed_categories": ["A", "B"]}, "non_oil_key", "model")
        second = self.new_job("non_oil")
        with second.connection() as cur:
            cur.execute("INSERT INTO inspection_report_non_oil_key_issue_classifications VALUES (1, 'B', 'manual', 'manual decision')")
        result = second.classifications(run, {"issues": [{"issue_id": 1}, {"issue_id": 3}], "allowed_categories": ["A", "B"]}, "non_oil_key", "model")
        self.assertEqual(batches, [[1, 2], [3]])
        self.assertEqual({item["issue_id"]: item["category"] for item in result["payload"]["classifications"]}, {1: "B", 3: "A"})

    def test_partial_classification_retries_only_missing_items_and_batches_25(self):
        memory = self.new_job("non_oil")
        batches = []
        def run(ctx):
            batches.append([item["issue_id"] for item in ctx["issues"]])
            return ai_result({"classifications": [{"issue_id": item["issue_id"], "category": "A"}
                                                   for item in ctx["issues"] if item["issue_id"] != 1]})
        ctx = {"issues": [{"issue_id": item} for item in range(1, 62)], "allowed_categories": ["A"]}
        memory.classifications(run, ctx, "quality_flow", "model")
        self.assertEqual(list(map(len, batches)), [25, 25, 11])
        memory.classifications(run, ctx, "quality_flow", "model")
        self.assertEqual(batches[-1], [1])

    def test_overlapping_concurrent_classifications_dont_charge_same_id_twice(self):
        calls = []
        def run(ctx):
            ids = [item["issue_id"] for item in ctx["issues"]]
            calls.extend(ids)
            time.sleep(0.15)
            return ai_result({"classifications": [{"issue_id": item, "category": "A"} for item in ids]})
        def job(ids):
            return self.new_job().classifications(run, {"issues": [{"issue_id": item} for item in ids],
                                                       "allowed_categories": ["A"]}, "non_oil_category", "model")
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(job, [[1, 2], [2, 3]]))
        self.assertEqual(sorted(calls), [1, 2, 3])

    def test_migration_twice_preserves_memory_and_downgrade_roundtrip(self):
        memory = self.new_job()
        memory.batch(lambda _: ai_result(finance_payload()), {"issues": [{"issue_id": 1}]}, "finance_insights", "v1", "model")
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                self.migration.upgrade()
                self.migration.upgrade()
                count = connection.execute(sa.text("SELECT COUNT(*) FROM inspection_report_ai_memory")).scalar()
                self.assertEqual(count, 1)
                self.migration.downgrade()
                self.migration.upgrade()

    def test_all_production_ai_wrappers_reuse_without_contacting_provider(self):
        import ai_utils
        from unittest.mock import MagicMock
        function_names = {
            "quality_insights": "generate_quality_measurement_report_insights",
            "safety_insights": "generate_safety_quality_report_insights",
            "finance_insights": "generate_finance_report_insights",
            "equipment_insights": "generate_equipment_facilities_report_insights",
            "service_insights": "generate_on_site_service_report_insights",
            "non_oil_insights": "generate_non_oil_report_insights",
        }
        client = MagicMock()
        with patch("ai_utils.get_deepseek_client", return_value=client):
            for operation, function_name in function_names.items():
                memory = self.new_job(operation)
                payload = {key: kind() for key, kind in INSIGHT_FIELDS[operation].items()}
                client.chat.completions.create.return_value.choices[0].message.content = json.dumps(payload)
                token = begin_report_ai_memory(self.connect, memory.task_id, operation)
                try:
                    function = getattr(ai_utils, function_name)
                    first = function({"issues": [{"issue_id": 1}]})
                    second = function({"issues": [{"issue_id": 1}]})
                    self.assertTrue(first["usage"]["ai_called"], operation)
                    self.assertFalse(second["usage"]["ai_called"], operation)
                    self.assertEqual(first["payload"], second["payload"], operation)
                finally:
                    end_report_ai_memory(token)
        self.assertEqual(client.chat.completions.create.call_count, 6)

    def test_context_scope_snapshot_and_existing_classification_reuse_logging(self):
        memory = self.new_job()
        token = begin_report_ai_memory(self.connect, memory.task_id, "finance")
        try:
            set_report_ai_evidence([{"id": 1, "description": "full"}])
            record_classification_reuse("quality_flow", {1: {"classification_source": "manual"},
                                                        2: {"classification_source": "fallback"}}, [{"id": 1}, {"id": 2}])
            @remember_report_ai("finance_insights", "system", lambda _: "prompt", "model")
            def generate(_):
                return ai_result(finance_payload())
            generate({"issues": [{"issue_id": 1}]})
            generate({"issues": [{"issue_id": 1}]})
            log = report_ai_generation_log()
            self.assertEqual(log["summary"]["ai_calls"], 1)
            self.assertEqual(log["summary"]["reused_classifications"], 1)
            self.assertEqual(log["summary"]["reuse_steps"], 2)
            from app import save_inspection_report_snapshot
            with patch("app.report_snapshot_table_available", return_value=True), patch("app.resolve_inspection_report_period", return_value=(date(2026, 7, 1), date(2026, 8, 1))):
                from unittest.mock import MagicMock
                cur = MagicMock()
                cur.fetchone.return_value = {"id": 1}
                report = save_inspection_report_snapshot(cur, "finance", "2026-07", "global", {}, {"id": 1})
                self.assertEqual(report["ai_generation_log"], log)
        finally:
            end_report_ai_memory(token)
        self.assertIsNone(report_ai_generation_log())


if __name__ == "__main__":
    unittest.main()
