"""Routing rules for the staged non-oil review, independent of final outcomes."""

AREA_REVIEW_ROLES = ("area_account", "area_non_oil")
SUPERVISION_ROLES = ("supervisor", "supervisor_manager")
FLOW_LABELS = {
    "non_oil_area_review_passed": "片区复核通过，转非油事业部终审",
    "non_oil_field_review_requested": "非油事业部转交督导中心现场复核",
    "non_oil_field_review_passed": "现场复核通过，返回非油事业部终审",
    "non_oil_field_review_returned": "现场复核不通过，返回非油事业部终审",
    "non_oil_department_returned": "非油事业部驳回，交片区退回站点",
    "non_oil_area_returned_to_station": "片区退回站点重新整改",
}


def stage_for(issue):
    return issue.get("non_oil_review_stage") or "area"


def token_for(issue):
    return str(issue.get("non_oil_review_event_id") or 0)


def department_queue_predicate(view=None):
    stage = {
        "area": "COALESCE(i.non_oil_review_stage, 'area') IN ('area', 'area_return')",
        "field": "i.non_oil_review_stage = 'field'",
    }.get(view, "i.non_oil_review_stage = 'department'")
    return "i.audit_status = 'approved' AND " + stage


def can_act(role, stage):
    return (
        (role in AREA_REVIEW_ROLES and stage in ("area", "area_return"))
        or (role == "non_oil" and stage == "department")
        or (role in SUPERVISION_ROLES and stage == "field")
    )


def advance(cur, issue_id, stage, event_id):
    cur.execute("""UPDATE issues SET non_oil_review_stage=%s, non_oil_review_event_id=%s
                   WHERE id=%s""", (stage, event_id, issue_id))


def review_route(stage, rejected):
    """Only the department can conclude; a department rejection is relayed by area."""
    if stage == 'field':
        return 'department', 'non_oil_field_review_returned' if rejected else 'non_oil_field_review_passed'
    if stage == 'department' and rejected:
        return 'area_return', 'non_oil_department_returned'
    if stage == 'area' and not rejected:
        return 'department', 'non_oil_area_review_passed'
    return None, 'non_oil_area_returned_to_station' if stage == 'area_return' else 'review_submitted'
