"""Regional account identities and the fixed visibility policy for specialists."""

AREA_SPECIALIST_DEPARTMENTS = {
    "area_oil_gas": "oil_gas",
    "area_non_oil": "non_oil",
    "area_safety": "quality_safety",
}
AREA_ROLE_LABELS = {
    "area_account": "片区经理",
    "area_oil_gas": "油气专员",
    "area_non_oil": "非油专员",
    "area_safety": "安全专员",
}
AREA_ROLES = tuple(AREA_ROLE_LABELS)
SPECIALIST_FIXED_ENABLED = frozenset({
    "limit_issue_station_region_scope", "limit_record_station_region_scope",
    "limit_issue_inspection_table_scope", "limit_record_inspection_table_scope",
    "hide_inspector_contact_info",
})
SPECIALIST_CONFIGURABLE = frozenset({"view_operations_overview"})
SPECIALIST_READ_ENDPOINTS = frozenset({
    "get_issues", "get_issue_filter_options", "get_issue_flow_history",
    "get_inspections", "get_inspection_filter_options", "get_inspection_issues",
    "get_inspection_tables", "highlights", "highlight_options",
    "list_issue_appeals", "operations",
})
SPECIALIST_EXPORT_ENDPOINTS = frozenset({
    "create_issue_export_task", "get_issue_export_task",
    "prepare_issue_export_download", "download_issue_export_task",
})


def specialist_api_allowed(endpoint, path, method):
    if path.startswith(("/api/auth/", "/api/notifications/", "/api/feedbacks/", "/api/feedback-comments/", "/api/help-documents/")):
        return True
    if path in {"/api/notifications", "/api/feedbacks", "/api/help-documents",
                "/api/users/change-password", "/api/system/resources", "/api/page-visibility"}:
        return True
    if endpoint in SPECIALIST_EXPORT_ENDPOINTS or endpoint == "mark_appeal_read":
        return True
    return method in {"GET", "HEAD"} and endpoint in SPECIALIST_READ_ENDPOINTS


def is_area_specialist(role):
    return role in AREA_SPECIALIST_DEPARTMENTS


def restrict_specialist_permissions(permissions):
    return {
        key: key in SPECIALIST_FIXED_ENABLED or (
            key in SPECIALIST_CONFIGURABLE and bool(enabled)
        )
        for key, enabled in permissions.items()
    }


def require_specialist_region(role, scopes):
    if not is_area_specialist(role):
        return
    region = scopes.get("limit_issue_station_region_scope", [])
    if len(region) != 1:
        raise ValueError("片区专员必须绑定一个所属片区。")


def specialist_can_read_media(cur, path, regions, tables):
    category = path.split("/", 1)[0]
    if category == "feedback_screenshots":
        return True  # Same public-function visibility as the feedback page.
    if not regions or not tables:
        return False
    stored_paths = [path, "/" + path]
    if category == "signatures":
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM inspections ins JOIN stations s ON s.id=ins.station_id
                WHERE ins.station_manager_signature_path=ANY(%s)
                  AND ins.inspection_table_id=ANY(%s)
                  AND COALESCE(NULLIF(TRIM(s.region), ''), '未填写片区')=ANY(%s)
                  AND NOT EXISTS (SELECT 1 FROM issues i WHERE i.inspection_id=ins.id
                                  AND COALESCE(i.audit_status, 'pending')='pending')
            ) AS allowed
        """, (stored_paths, list(tables), list(regions)))
    elif category in ("issues", "rectifications"):
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM issues i JOIN stations s ON s.id=i.station_id
                WHERE (i.photo_path=ANY(%s) OR i.rectification_photo_path=ANY(%s) OR i.review_photo_path=ANY(%s)
                       OR EXISTS (SELECT 1 FROM inspection_issue_flow_history h
                                  WHERE h.issue_id=i.id AND h.photo_path=ANY(%s)))
                  AND i.inspection_table_id=ANY(%s)
                  AND COALESCE(NULLIF(TRIM(s.region), ''), '未填写片区')=ANY(%s)
                  AND COALESCE(i.audit_status, 'pending')<>'pending'
                UNION ALL
                SELECT 1 FROM inspection_highlights h JOIN stations s ON s.id=h.station_id
                WHERE h.photo_path=ANY(%s) AND h.inspection_table_id=ANY(%s)
                  AND COALESCE(NULLIF(TRIM(s.region), ''), '未填写片区')=ANY(%s)
                  AND COALESCE(h.audit_status, 'pending')<>'pending'
            ) AS allowed
        """, (stored_paths, stored_paths, stored_paths, stored_paths, list(tables), list(regions),
              stored_paths, list(tables), list(regions)))
    else:
        return False
    return bool(cur.fetchone()["allowed"])
