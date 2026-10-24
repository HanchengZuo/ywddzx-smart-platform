"""Report perspectives do not broaden permissions on other inspection pages."""

DEPARTMENT_REPORT_TYPES = {
    "quality_safety": ("quality_measurement", "safety_quality"),
    "development_plan": ("equipment_facilities",),
    "oil_gas": ("on_site_service",),
    "non_oil": ("non_oil",),
    "finance": ("finance",),
}


def report_perspective(user, permissions):
    if user.get("role") == "root" or permissions.get("view_inspection_reports"):
        return "center"
    if (permissions.get("view_department_inspection_reports")
            and user.get("role") in DEPARTMENT_REPORT_TYPES):
        return "department"
    return None


def allowed_report_types(user, permissions, available):
    perspective = report_perspective(user, permissions)
    if perspective == "center":
        return tuple(available)
    if perspective == "department":
        return tuple(key for key in available if key in DEPARTMENT_REPORT_TYPES[user["role"]])
    return ()
