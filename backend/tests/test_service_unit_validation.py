import unittest
from service_report_unit_validation import (
    unit_item,
    confirmed_items,
    repair_context,
    UnitEvidenceValidationError,
)


def group(ref="G1", count=2):
    return {
        "ref": ref,
        "issues": [
            {"ref": f"I{100+i}", "issue_id": 100 + i, "photo": True}
            for i in range(count)
        ],
    }


class UnitPhotoValidationTests(unittest.TestCase):
    def test_single_and_empty_candidates_are_server_owned(self):
        self.assertEqual(
            unit_item({"summary": "实际表现", "photo_ids": ["I1"]}, group(count=1))[
                "photo_ids"
            ],
            ["I100"],
        )
        self.assertEqual(
            unit_item({"summary": "实际表现"}, group(count=1))["photo_ids"], ["I100"]
        )
        self.assertEqual(
            unit_item({"summary": "实际表现", "photo_ids": ["I999"]}, group(count=0))[
                "photo_ids"
            ],
            [],
        )

    def test_numeric_ids_and_valid_ranked_shortlists_are_canonical_not_positional(self):
        for values in [[101], ["101"], [" I101 "], ["101", "I100", "101"]]:
            self.assertEqual(
                unit_item({"summary": "实际表现", "photo_ids": values}, group())[
                    "photo_ids"
                ],
                ["I101"],
            )
        for values in [
            ["I1"],
            [999],
            [True],
            ["I100", "I999"],
            [{"issue_id": 100}],
            [],
        ]:
            with self.assertRaises(UnitEvidenceValidationError):
                unit_item({"summary": "实际表现", "photo_ids": values}, group())

    def test_refusal_for_outside_group_or_non_photo_issue(self):
        entry = group()
        entry["issues"].append({"ref": "I999", "issue_id": 999, "photo": False})
        with self.assertRaises(UnitEvidenceValidationError):
            unit_item({"summary": "实际表现", "photo_ids": [999]}, entry)
        for text in ["", "x" * 161, None]:
            with self.assertRaises(UnitEvidenceValidationError):
                unit_item({"summary": text}, group(count=1))

    def test_targeted_repair_includes_exact_candidates_and_previous_output(self):
        context = {"kind": "unit_evidence", "items": [group("G1", 1), group("G2")]}
        old = {
            "items": {
                "G1": {"summary": "第一组实际表现", "photo_ids": []},
                "G2": {"summary": "第二组实际表现", "photo_ids": ["I999"]},
            }
        }
        good, bad = confirmed_items(old, context)
        self.assertEqual(set(good), {"G1"})
        self.assertEqual(set(bad), {"G2"})
        retry = repair_context(context, bad, old)
        self.assertEqual([g["ref"] for g in retry["items"]], ["G2"])
        self.assertEqual(retry["items"][0]["allowed_photo_refs"], ["I100", "I101"])
        self.assertEqual(retry["items"][0]["previous_result"], old["items"]["G2"])
        self.assertNotIn("allowed_photo_refs", context["items"][1])
