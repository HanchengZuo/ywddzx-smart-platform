"""Canonical, group-bound photo references; deterministic fields are server-owned."""

from copy import deepcopy


class UnitEvidenceValidationError(ValueError):
    pass


def unit_item(value, group):
    ref = group["ref"]
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("summary"), str)
        or not value["summary"].strip()
        or len(value["summary"]) > 160
    ):
        raise UnitEvidenceValidationError(f"{ref} 环节概括须为1至160字。")
    allowed = [row["ref"] for row in group["issues"] if row["photo"]]
    # There is no selection decision with zero/one candidate. Never depend on
    # a provider inventing the correct ref for these server-known fields.
    if len(allowed) <= 1:
        photos = allowed
    else:
        values = value.get("photo_ids")
        if not isinstance(values, list) or not values:
            raise UnitEvidenceValidationError(f"{ref} 须选择一张本环节候选照片。")
        aliases = {
            str(row["issue_id"]): row["ref"]
            for row in group["issues"]
            if row["photo"] and row.get("issue_id") is not None
        }
        normalized = []
        for identifier in values:
            if type(identifier) is int:
                identifier = str(identifier)
            if isinstance(identifier, str):
                identifier = aliases.get(identifier.strip(), identifier.strip())
            if not isinstance(identifier, str) or identifier not in allowed:
                raise UnitEvidenceValidationError(
                    f"{ref} 代表照片引用了本环节候选范围外的问题。"
                )
            if identifier not in normalized:
                normalized.append(identifier)
        # Some providers return a ranked shortlist despite the one-photo limit.
        # Every member must be valid before taking the first ranked candidate.
        photos = normalized[:1]
    return {"summary": value["summary"].strip(), "photo_ids": photos}


def confirmed_items(payload, context):
    items = payload.get("items") if isinstance(payload, dict) else None
    confirmed, failures = {}, {}
    for group in context["items"]:
        ref = group["ref"]
        try:
            confirmed[ref] = unit_item(
                items.get(ref) if isinstance(items, dict) else None, group
            )
        except UnitEvidenceValidationError as exc:
            failures[ref] = str(exc)
    if isinstance(items, dict) and set(items) - {g["ref"] for g in context["items"]}:
        # Unknown group keys are not silently mapped by position.
        failures["__groups__"] = "AI返回了范围外的环节标识。"
    return confirmed, failures


def repair_context(context, failures, previous):
    evidence = deepcopy(context)
    if "__groups__" not in failures:
        evidence["items"] = [g for g in evidence["items"] if g["ref"] in failures]
    evidence["validation_errors"] = failures
    old = previous.get("items") if isinstance(previous, dict) else {}
    for group in evidence["items"]:
        group["allowed_photo_refs"] = [
            row["ref"] for row in group["issues"] if row["photo"]
        ]
        group["required_photo_count"] = min(1, len(group["allowed_photo_refs"]))
        if isinstance(old, dict):
            group["previous_result"] = old.get(group["ref"])
    return evidence
