"""Persistent report AI results, scoped to an authenticated background job."""

import copy
import hashlib
import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps

from psycopg2.extras import Json, RealDictCursor

from ai_usage import build_ai_usage_meta


_current = ContextVar("report_ai_memory", default=None)
MEMORY_VERSION = 1
CLASSIFICATION_TABLES = {
    "quality_flow": "inspection_report_quality_issue_classifications",
    "non_oil_category": "inspection_report_non_oil_issue_classifications",
    "non_oil_key": "inspection_report_non_oil_key_issue_classifications",
}
STAGE_LABELS = {
    "quality_flow": "质量计量问题环节分类",
    "non_oil_category": "非油其他问题分类",
    "non_oil_key": "非油重点问题分类",
    "quality_insights": "质量计量选题、管理追溯与工作计划",
    "safety_insights": "安全质量典型问题、分析与建议",
    "finance_insights": "财务检查结果分析与建议",
    "equipment_insights": "设备设施典型问题、分析与建议",
    "service_insights": "现场服务重点问题、总结与建议",
    "non_oil_insights": "非油典型问题、归因分析与改善建议",
}
INSIGHT_FIELDS = {
    "quality_insights": {"management_trace": dict, "work_plan": list, "prohibited_decisions": list},
    "safety_insights": {"typical_issues": list, "category_highlights": list,
                        "problem_analysis": list, "work_suggestions": list},
    "finance_insights": {"result_analysis": list, "content_suggestions": list},
    "equipment_insights": {"typical_issue": dict, "problem_analysis": list, "work_suggestions": list},
    "service_insights": {"region_highlights": list, "problem_summary": list, "next_steps": list},
    "non_oil_insights": {"unit_highlights": list, "typical_issues": list, "core_findings": list,
                         "attribution_analysis": list, "improvement_suggestions": list,
                         "action_priorities": list},
}


def canonical(value):
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        items = [canonical(item) for item in value]
        # Query order is not meaningful; priority lists and category order are.
        for key in ("issue_id", "id"):
            if items and all(isinstance(item, dict) and key in item for item in items):
                return sorted(items, key=lambda item: int(item[key]))
        return items
    return value


def fingerprint(value):
    encoded = json.dumps(canonical(value), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def issue_ids(value):
    result = set()
    if isinstance(value, dict):
        if value.get("issue_id"):
            result.add(int(value["issue_id"]))
        for item in value.values():
            result.update(issue_ids(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            result.update(issue_ids(item))
    return sorted(result)


class ReportMemoryUnavailable(RuntimeError):
    pass


class ReportMemory:
    def __init__(self, connect, task_id, report_type):
        self.connect = connect
        self.task_id = task_id
        self.report_type = report_type
        self.events = []
        self.evidence = None

    @contextmanager
    def connection(self):
        conn = self.connect()
        try:
            # Advisory session locks must not leave a transaction open during AI.
            conn.autocommit = True
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                yield cur
        finally:
            conn.close()

    def snapshot(self):
        return {
            "version": MEMORY_VERSION,
            "task_id": self.task_id,
            "events": copy.deepcopy(self.events),
            "summary": {
                "ai_calls": sum(bool(e.get("ai_called")) for e in self.events),
                "reuse_steps": sum(e["outcome"] in {"cache_hit", "classification_reuse"}
                                  for e in self.events),
                "reused_classifications": sum(e.get("issue_count", 0) for e in self.events
                                              if e["outcome"] == "classification_reuse"),
                "fallback_steps": sum(e["outcome"] in {"fallback", "error"}
                                      for e in self.events),
            },
        }

    def record(self, operation, outcome, message, **details):
        self.events.append({
            "sequence": len(self.events) + 1,
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": STAGE_LABELS.get(operation, operation),
            "outcome": outcome,
            "message": message,
            **details,
        })
        with self.connection() as cur:
            cur.execute("UPDATE inspection_report_jobs SET ai_generation_log = %s WHERE task_id = %s",
                        (Json(self.snapshot()), self.task_id))

    @contextmanager
    def locked(self, key):
        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        with self.connection() as cur:
            deadline = time.monotonic() + 600
            while True:
                cur.execute("SELECT pg_try_advisory_lock(%s) AS acquired", (lock_id,))
                if cur.fetchone()["acquired"]:
                    break
                if time.monotonic() >= deadline:
                    raise ReportMemoryUnavailable("同类AI任务仍在处理，请稍后重试；未重复发起AI请求。")
                time.sleep(0.25)
            try:
                yield cur
            finally:
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))

    def get(self, cur, key):
        cur.execute("SELECT payload, created_at, source_task_id FROM inspection_report_ai_memory WHERE cache_key = %s",
                    (key,))
        return cur.fetchone()

    def put(self, cur, key, operation, ids, payload, model):
        cur.execute("""
            INSERT INTO inspection_report_ai_memory
                (cache_key, operation, report_type, issue_ids, payload, model, source_task_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET payload = EXCLUDED.payload,
                model = EXCLUDED.model, source_task_id = EXCLUDED.source_task_id,
                created_at = CURRENT_TIMESTAMP
        """, (key, operation, self.report_type, ids, Json(payload), model, self.task_id))

    def call(self, function, context, operation, model):
        started = time.monotonic()
        self.record(operation, "pending", "未找到可用历史结果，正在尝试调用AI处理缺失的分析或分类。",
                    issue_count=len(issue_ids(context)))
        try:
            result = function(context)
        except Exception:
            self.record(operation, "error", "AI处理异常，未保存可复用结果。",
                        elapsed_ms=round((time.monotonic() - started) * 1000))
            raise
        usage = result.get("usage") or {}
        self.record(operation, "ai_result" if successful(result) else "fallback",
                    "AI处理完成，成功结果已进入持久化复用流程。" if successful(result)
                    else "AI未返回有效结果；本地兜底不会作为成功AI记忆保存。",
                    issue_count=len(issue_ids(context)), ai_called=bool(usage.get("ai_called")),
                    model=model, elapsed_ms=round((time.monotonic() - started) * 1000),
                    input_tokens_est=usage.get("input_tokens_est", 0),
                    output_tokens_est=usage.get("output_tokens_est", 0),
                    cost_est=usage.get("total_cost_est", 0))
        return result

    def batch(self, function, context, operation, signature, model):
        ids = sorted(set(issue_ids(context)) | set((self.evidence or {}).get("issue_ids", [])))
        key = fingerprint({"version": MEMORY_VERSION, "operation": operation,
                           "signature": signature, "model": model, "context": context,
                           "issue_ids": ids, "evidence": self.evidence})
        with self.locked("report-ai:" + key) as cur:
            stored = self.get(cur, key)
            if stored:
                self.record(operation, "cache_hit", "问题ID、内容及分析输入一致，复用历史AI选题和分析文本，未调用AI。",
                            issue_count=len(ids), source_task_id=stored["source_task_id"],
                            source_generated_at=str(stored["created_at"]))
                return reused_result(stored["payload"], model)
            result = self.call(function, context, operation, model)
            if successful(result) and valid_insights(result["payload"], operation, set(ids)):
                self.put(cur, key, operation, ids, result["payload"], model)
            elif successful(result):
                self.record(operation, "fallback", "返回内容结构不完整或包含无效问题引用，未存入AI记忆；报告按已有校验规则处理。",
                            issue_count=len(ids))
            return result

    def classifications(self, function, context, operation, model):
        candidates = {int(item["issue_id"]): item for item in context.get("issues", [])}
        allowed = context.get("allowed_categories") or []
        decisions = {}
        # Serialize only the short classification batches, not whole report jobs.
        with self.locked("report-ai-classification:" + operation) as cur:
            table = CLASSIFICATION_TABLES[operation]
            cur.execute(f"""SELECT issue_id, effective_category AS category, reason
                FROM {table} WHERE issue_id = ANY(%s)
                AND classification_source IN ('ai', 'manual')""", (list(candidates),))
            for item in cur.fetchall():
                if item["category"] in allowed:
                    decisions[int(item["issue_id"])] = dict(item)
            keys = {item_id: fingerprint(["classification", operation, item_id]) for item_id in candidates}
            for item_id in candidates:
                if item_id in decisions:
                    continue
                saved = self.get(cur, keys[item_id])
                if saved and saved["payload"].get("category") in allowed:
                    decisions[item_id] = saved["payload"]
            if decisions:
                self.record(operation, "classification_reuse", "按全局问题ID复用历史分类，人工调整结果优先，未重复调用AI。",
                            issue_count=len(decisions))
            pending = [item for item_id, item in candidates.items() if item_id not in decisions]
            aggregate_usage = build_ai_usage_meta(model, success=True)
            for offset in range(0, len(pending), 25):
                batch = pending[offset:offset + 25]
                result = self.call(function, {**context, "issues": batch}, operation, model)
                usage = result.get("usage") or {}
                for name, value in usage.items():
                    if name.endswith(("_est", "_chars")) or name == "total_chars":
                        aggregate_usage[name] = aggregate_usage.get(name, 0) + (value or 0)
                aggregate_usage["ai_called"] |= bool(usage.get("ai_called"))
                valid = valid_classifications(result, {int(item["issue_id"]) for item in batch}, allowed)
                for item_id, decision in valid.items():
                    self.put(cur, keys[item_id], operation, [item_id], decision, model)
                    decisions[item_id] = decision
                if len(valid) != len(batch):
                    self.record(operation, "fallback", "部分分类无效或缺失，仅保存有效分类；其余交由本地规则处理，下次可重试。",
                                issue_count=len(batch) - len(valid))
            aggregate_usage["success"] = len(decisions) == len(candidates)
            aggregate_usage["fallback_used"] = not aggregate_usage["success"]
            return {"generated": bool(decisions), "message": "已读取或生成问题分类。",
                    "payload": {"classifications": list(decisions.values())}, "usage": aggregate_usage}


def successful(result):
    return bool(result and result.get("generated") and isinstance(result.get("payload"), dict)
                and result["payload"] and (result.get("usage") or {}).get("success")
                and not (result.get("usage") or {}).get("fallback_used"))


def valid_insights(payload, operation, eligible):
    fields = INSIGHT_FIELDS.get(operation, {})
    if not fields or not all(isinstance(payload.get(key), kind) for key, kind in fields.items()):
        return False

    def references_valid(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("issue_ids"):
                    if not isinstance(item, list) or any(not valid_id(ref) for ref in item):
                        return False
                elif key.endswith("issue_id") and not valid_id(item):
                    return False
                elif not references_valid(item):
                    return False
        elif isinstance(value, list):
            return all(references_valid(item) for item in value)
        return True

    def valid_id(value):
        try:
            return int(value) in eligible
        except (TypeError, ValueError):
            return False

    return references_valid(payload)


def valid_classifications(result, eligible, allowed):
    if not successful(result):
        return {}
    records = result["payload"].get("classifications")
    if not isinstance(records, list):
        return {}
    valid, duplicates = {}, set()
    for item in records:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("issue_id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id in valid:
            duplicates.add(item_id)
        category = str(item.get("category") or "").strip()
        if item_id in eligible and category in allowed:
            valid[item_id] = {"issue_id": item_id, "category": category,
                              "reason": str(item.get("reason") or "AI分类结果")[:500]}
    return {key: item for key, item in valid.items() if key not in duplicates}


def reused_result(payload, model):
    return {"generated": True, "message": "已复用历史AI结果，本次未调用AI。",
            "payload": copy.deepcopy(payload), "usage": build_ai_usage_meta(model, success=True)}


def remember_report_ai(operation, system_prompt, prompt_builder, model):
    def decorate(function):
        @wraps(function)
        def wrapped(context):
            memory = _current.get()
            if memory is None:
                return function(context)
            if operation in CLASSIFICATION_TABLES:
                return memory.classifications(function, context or {}, operation, model)
            signature = fingerprint([system_prompt, prompt_builder(canonical(context or {}))])
            return memory.batch(function, context or {}, operation, signature, model)
        return wrapped
    return decorate


def begin_report_ai_memory(connect, task_id, report_type):
    memory = ReportMemory(connect, task_id, report_type)
    try:
        with memory.connection() as cur:
            cur.execute("SELECT cache_key FROM inspection_report_ai_memory LIMIT 0")
        memory.record("生成任务", "info", "开始生成；按问题ID和分析输入检查历史记忆，统计与PPT仍按本次数据编排。")
    except Exception as exc:
        raise ReportMemoryUnavailable("AI报告记忆存储不可用，请检查数据库迁移；为避免重复计费，未发起AI请求。") from exc
    return _current.set(memory)


def end_report_ai_memory(token):
    if token is not None:
        _current.reset(token)


def set_report_ai_evidence(rows, settings=None):
    memory = _current.get()
    if memory:
        memory.evidence = {
            "issue_ids": sorted({int(row.get("issue_id") or row.get("id") or 0)
                                 for row in rows if row.get("issue_id") or row.get("id")}),
            "rows": rows,
            "settings": settings,
        }


def report_ai_generation_log():
    memory = _current.get()
    return memory.snapshot() if memory else None


def record_classification_reuse(operation, classification_map, rows):
    memory = _current.get()
    if not memory:
        return
    ids = {int(row.get("id") or 0) for row in rows}
    reused = [value for key, value in classification_map.items()
              if int(key) in ids and value.get("classification_source") in {"ai", "manual"}]
    if reused:
        manual = sum(item.get("classification_source") == "manual" for item in reused)
        memory.record(operation, "classification_reuse",
                      f"按问题ID读取{len(reused)}条持久分类（其中人工调整{manual}条），无需AI重分。",
                      issue_count=len(reused))
