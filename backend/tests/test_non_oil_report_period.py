import unittest
from datetime import date

from app import parse_non_oil_report_period, resolve_non_oil_report_period


class NonOilReportPeriodTest(unittest.TestCase):
    def test_default_period_uses_calendar_month(self):
        self.assertEqual(
            parse_non_oil_report_period("2026-07"),
            (date(2026, 7, 1), date(2026, 8, 1)),
        )

    def test_custom_period_remains_inclusive(self):
        self.assertEqual(
            resolve_non_oil_report_period(
                "2026-07",
                {"date_from": "2026-06-26", "date_to": "2026-07-29"},
            ),
            (date(2026, 6, 26), date(2026, 7, 30)),
        )


if __name__ == "__main__":
    unittest.main()
