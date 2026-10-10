"""Validate multi-standard selections while retaining legacy single-standard requests."""
import json
import re

MAX_SELECTED_STANDARDS = 100


def parse_standard_selections(form):
    raw = form.get("standards")
    if raw is None:
        entries = [{"standard_id": form.get("standard_id"),
                    "internal_standard_id": form.get("internal_standard_id"),
                    "inspection_table_id": form.get("inspection_table_id")}]
    else:
        try:
            entries = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("规范多选数据格式不正确，请重新选择。") from exc
        if not isinstance(entries, list) or not entries:
            raise ValueError("请至少选择一条规范。")
        if len(entries) > MAX_SELECTED_STANDARDS:
            raise ValueError(f"一次最多选择{MAX_SELECTED_STANDARDS}条规范。")
    selections, seen = [], {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("规范多选数据格式不正确。")
        internal = str(entry.get("internal_standard_id") or "").strip().upper()
        external = str(entry.get("standard_id") or "").strip()
        table = str(entry.get("inspection_table_id") or "").strip()
        if internal and external:
            raise ValueError("一条选择不能同时指定内部和外部规范。")
        if internal:
            if len(internal) > 100:
                raise ValueError("内部规范ID格式不正确。")
            key = ("internal", internal)
            item = {"internal_standard_id": internal}
        else:
            if not re.fullmatch(r"\d{1,18}", external) or int(external) <= 0:
                raise ValueError("请选择有效的外部规范ID。")
            external = str(int(external))
            if table and (not re.fullmatch(r"\d{1,10}", table) or int(table) <= 0):
                raise ValueError("检查表ID格式不正确。")
            key = ("external", external)
            item = {"standard_id": external, "inspection_table_id": table}
        if key in seen:
            # Conflicting table claims must not be hidden by deduplication.
            previous = seen[key]
            if key[0] == "external" and previous["inspection_table_id"] != table:
                raise ValueError("同一规范的检查表信息不一致。")
            continue
        seen[key] = item
        selections.append(item)
    return selections
