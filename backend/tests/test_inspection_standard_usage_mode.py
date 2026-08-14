import unittest

from app import get_inspection_standard_usage_mode


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return next(self.rows)


def build_usage_mode_cursor(has_active_internal_standard):
    return FakeCursor(
        [
            {"table_name": "inspection_standard_usage_settings"},
            {
                "register_standard_source": "internal",
                "updated_by": 1,
                "updated_by_username": "root",
                "updated_by_name": "系统管理员",
                "updated_at": "2026-08-14 10:00",
            },
            {"table_name": "inspection_internal_standards"},
            {"has_active": has_active_internal_standard},
        ]
    )


class InspectionStandardUsageModeTests(unittest.TestCase):
    def test_empty_internal_library_falls_back_to_external_for_registration(self):
        usage_mode = get_inspection_standard_usage_mode(build_usage_mode_cursor(False))

        self.assertEqual(usage_mode["configured_mode"], "internal")
        self.assertEqual(usage_mode["mode"], "external")
        self.assertTrue(usage_mode["is_fallback"])
        self.assertIn("暂无启用规范", usage_mode["fallback_reason"])

    def test_active_internal_library_keeps_configured_mode(self):
        usage_mode = get_inspection_standard_usage_mode(build_usage_mode_cursor(True))

        self.assertEqual(usage_mode["configured_mode"], "internal")
        self.assertEqual(usage_mode["mode"], "internal")
        self.assertFalse(usage_mode["is_fallback"])


if __name__ == "__main__":
    unittest.main()
