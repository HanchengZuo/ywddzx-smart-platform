import unittest
from copy import deepcopy
from issue_flow_presentation import present_flow_rows, flow_event_presentation


class FlowPresentationTests(unittest.TestCase):
    def test_only_same_transaction_state_rows_are_collapsed(self):
        event = dict(occurred_at='2026-09-06T10:00:01', actor_user_id=1,
                     from_status='申诉中', to_status='待整改')
        rows = [dict(event, action_type='status_changed'),
                dict(event, action_type='appeal_quality_rejected'),
                dict(event, action_type='status_changed', occurred_at='2026-09-06T10:00:02')]
        original = deepcopy(rows)
        rendered = present_flow_rows(rows)
        self.assertEqual([r['action_type'] for r in rendered], ['appeal_quality_rejected', 'status_changed'])
        self.assertEqual(rows, original)
        self.assertNotIn('occurred_at', rendered[0])

    def test_final_approval_is_one_event_not_an_audit_rejection(self):
        base = dict(occurred_at='t1', actor_user_id=1)
        rows = [dict(base, action_type='audit_changed', result='审核否决'),
                dict(base, action_type='appeal_quality_approved')]
        self.assertEqual(len(present_flow_rows(rows)), 1)
        rows[0]['actor_user_id'] = 2
        self.assertEqual(len(present_flow_rows(rows)), 2)

    def test_missing_timestamp_does_not_merge_evidence(self):
        rows = [dict(action_type='status_changed'), dict(action_type='appeal_submitted')]
        self.assertEqual(len(present_flow_rows(rows)), 2)

    def test_historic_repeat_is_explained(self):
        rows = [dict(action_type='appeal_submitted'), dict(action_type='appeal_area_rejected'),
                dict(action_type='appeal_submitted')]
        result = present_flow_rows(rows)
        self.assertEqual(result[-1]['appeal_attempt'], 2)
        self.assertIn('旧版本', result[-1]['history_notice'])
        self.assertEqual(flow_event_presentation(result[-1])['stage_label'], '历史第2次申诉')

    def test_actual_audit_redecision_is_not_an_appeal_decision(self):
        event = flow_event_presentation(dict(action_type='audit_changed', from_status='审核否决', result='审核通过'))
        self.assertEqual(event['action_label'], '问题重新判定：审核通过')
        self.assertIn('非申诉审核', event['stage_label'])
