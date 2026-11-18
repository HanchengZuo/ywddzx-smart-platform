"""Immutable review actors across queues, exports, resubmissions and history."""
import os
import unittest
from contextlib import ExitStack
from io import BytesIO
from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2.extras import RealDictCursor

import app as api
from issue_review_identity import attach_reviewers, attach_role_reviews, ROLE_REVIEW_KEYS, ROLE_REVIEW_COLUMNS
from tests import test_issue_review_workflow as review_tests


class ReviewIdentityTests(unittest.TestCase):
    def test_other_roles_neither_fetch_nor_receive_role_review_fields(self):
        for role in api.ROLE_OPTIONS:
            if role=='non_oil': continue
            cur=MagicMock()
            row=dict(id=1)
            attach_role_reviews(cur,[row],dict(role=role),api.ROLE_LABELS)
            self.assertEqual(row,dict(id=1))
            cur.execute.assert_not_called()

    def test_role_review_xlsx_contains_three_sets_of_text_and_optional_photos(self):
        from openpyxl import load_workbook
        import tempfile
        from pathlib import Path
        from PIL import Image
        stream=BytesIO()
        row=dict(id=1,inspection_table_id=1,inspection_table_name='非油检查表')
        row.update({key:'证据 '+key for key in ROLE_REVIEW_KEYS})
        with tempfile.TemporaryDirectory() as directory:
            for group,color in [('area','red'),('department','green'),('field','blue')]:
                path=Path(directory)/(group+'.png')
                Image.new('RGB',(20,20),color).save(path)
                row[group+'_review_photo']=str(path)
            options=api.normalize_issue_export_options(dict(include_fields=dict.fromkeys(ROLE_REVIEW_KEYS,True),
                include_photos=dict.fromkeys(api.ISSUE_EXPORT_PHOTO_KEYS,True)))
            with patch.object(api,'resolve_storage_abs_path',side_effect=lambda value:value):
                api.write_issue_export_xlsx(stream,[row],options,{})
            stream.seek(0)
            book=load_workbook(stream)
            try:
                values=list(book.active.values)
                self.assertEqual(values[0],tuple(label for label,_ in ROLE_REVIEW_COLUMNS))
                for index,(_,key) in enumerate(ROLE_REVIEW_COLUMNS):
                    if not key.endswith('_photo'): self.assertEqual(values[1][index],row[key])
                self.assertEqual(len(book.active._images),3)
            finally: book.close()
    def test_unreviewed_page_does_not_read_history_or_keep_stale_identity(self):
        cur=MagicMock()
        rows=[dict(id=1,review_at=None,reviewer='过期身份')]
        self.assertEqual(attach_reviewers(cur,rows,api.ROLE_LABELS)[0]['reviewer'],'')
        cur.execute.assert_not_called()

    def test_export_column_and_selection_are_before_review_time(self):
        columns=api.ISSUE_EXPORT_BASE_COLUMNS_AFTER_STANDARD
        index=columns.index(('问题复核时间','review_at'))
        self.assertEqual(columns[index-1],('问题复核人员','reviewer'))
        self.assertTrue(api.normalize_issue_export_options({})['include_fields']['reviewer'])
        for label in ('问题复核结果','问题复核说明','问题复核照片'):
            self.assertIn(label,dict(columns))

    def test_real_xlsx_has_neutral_headers_and_department_name_in_the_correct_column(self):
        from openpyxl import load_workbook
        stream=BytesIO()
        row=dict(id=1,inspection_table_id=1,inspection_table_name='测试表',review_result='整改通过',
                 review_note='说明',reviewer='质安部 · 原姓名',review_at='2026-11-05 10:00')
        options=api.normalize_issue_export_options({'include_fields':
            dict(review_result=True,review_note=True,reviewer=True,review_at=True)})
        api.write_issue_export_xlsx(stream,[row],options,{})
        stream.seek(0)
        book=load_workbook(stream,read_only=True)
        try:
            values=list(book.active.values)
            self.assertEqual(values[0],('问题复核结果','问题复核说明','问题复核人员','问题复核时间'))
            self.assertEqual(values[1],('整改通过','说明','质安部 · 原姓名','2026-11-05 10:00'))
        finally:
            book.close()

    def test_all_review_roles_use_generic_events_and_snapshot_departments(self):
        for role,label in [('supervisor','督导中心'),('supervisor_manager','督导中心'),
                           ('quality_safety','质安部'),('development_plan','发展计划部'),
                           ('oil_gas','油气事业部'),('finance','财务部'),('non_oil','非油事业部')]:
            for result in ('整改通过','整改不通过','通过站级无法整改','驳回站级无法整改'):
                event=api.serialize_issue_flow_history_event(dict(action_type='review_submitted',
                    actor_role=role,actor_name='原姓名',result=result,round_no=2))
                self.assertEqual(event['actor_department'],label)
                self.assertEqual(event['actor_display_name'],'原姓名')
                self.assertEqual(event['stage_label'],'问题复核')
                self.assertNotIn('督导',event['action_label'])
                self.assertEqual(event['tone'],'returned' if result in ('整改不通过','驳回站级无法整改') else 'success')
        event=api.serialize_issue_flow_history_event(dict(action_type='review_submitted',result='整改通过'))
        self.assertEqual(event['actor_display_name'],'历史数据')
        self.assertEqual(event['actor_department'],'')


@unittest.skipUnless(os.getenv('INSPECTION_SCHEDULE_DB_TEST')=='1','isolated database opt-in')
class ReviewIdentityDatabaseTests(unittest.TestCase):
    tearDown=review_tests.UnableClosureDatabaseTests.tearDown

    def setUp(self):
        review_tests.UnableClosureDatabaseTests.setUp(self)
        self.cur.execute("""
            SET TIME ZONE 'Asia/Shanghai';
            ALTER TABLE inspection_tables ADD COLUMN is_active boolean DEFAULT true;
            ALTER TABLE inspection_issue_flow_history DROP CONSTRAINT inspection_issue_flow_history_actor_user_id_fkey;
            ALTER TABLE inspection_issue_flow_history ADD FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL;
            UPDATE users SET role='quality_safety';
            UPDATE inspection_tables SET table_name='质量安全环保检查表（现场）';
            UPDATE issues SET rectification_result='已整改';
        """)
        review_tests.mark_quality_handoff(self.cur, 42)
        self.admin.commit()

    def connect(self):
        return psycopg2.connect(**self.config,cursor_factory=RealDictCursor,
            options=f'-c search_path={self.schema} -c timezone=Asia/Shanghai')

    def test_role_evidence_reads_latest_per_role_without_losing_earlier_actors(self):
        for role,result,note in [('area_non_oil','整改通过','片区意见'),('supervisor','整改不通过','现场意见'),
                                 ('non_oil','整改不通过','终审意见'),('supervisor_manager','整改通过','现场新意见')]:
            api.record_issue_workflow_event(self.cur,42,dict(id=17,role=role,real_name=role),
                'review_submitted','待复核','待复核',result,note,'rectifications/'+role+'.png')
        self.cur.execute("UPDATE users SET real_name='后来改名',role='finance' WHERE id=17")
        row=attach_role_reviews(self.cur,[dict(id=42)],dict(role='non_oil'),api.ROLE_LABELS)[0]
        self.assertEqual(row['area_review_note'],'片区意见')
        self.assertEqual(row['department_review_note'],'终审意见')
        self.assertEqual(row['field_review_note'],'现场新意见')
        self.assertEqual(row['field_review_photo'],'rectifications/supervisor_manager.png')
        self.assertNotIn('后来改名',row['field_review_reviewer'])
        self.assertEqual(row['review_note'],'现场新意见')
        api.record_issue_workflow_event(self.cur,42,dict(id=17,role='station_manager'),
            'rectification_submitted','待整改','待复核','已整改','新一轮整改')
        next_round=attach_role_reviews(self.cur,[dict(id=42)],dict(role='non_oil'),api.ROLE_LABELS)[0]
        self.assertNotIn('review_result',next_round)
        self.assertEqual(next_round['field_review_note'],'现场新意见')

    def submit(self, result='整改不通过'):
        with ExitStack() as stack:
            stack.enter_context(patch.object(api,'get_db_connection',side_effect=self.connect))
            stack.enter_context(patch.object(api,'get_authenticated_request_user_id',return_value=17))
            stack.enter_context(patch.object(api,'ensure_issue_inspector_schema'))
            stack.enter_context(patch.object(api,'has_permission',return_value=True))
            stack.enter_context(api.app.test_request_context('/api/issues/42/review',method='POST',
                data=dict(review_result=result,review_note='再次整改')))
            value=api.submit_review(42)
            response,status=value if isinstance(value,tuple) else (value,200)
            return response.get_json(),status

    def identity(self):
        self.cur.execute('SELECT id,review_at,review_result FROM issues WHERE id=42')
        return attach_reviewers(self.cur,[dict(self.cur.fetchone())],api.ROLE_LABELS)[0]

    def test_real_submission_reads_actor_snapshot_even_after_rename_role_change_and_deletion(self):
        body,status=self.submit()
        self.assertEqual(status,200,body)
        self.cur.execute("UPDATE users SET real_name='后来改名',role='finance' WHERE id=17")
        self.admin.commit()
        identity=self.identity()
        self.assertEqual(identity['reviewer'],'质安部 · 复核人员')
        self.assertEqual(identity['reviewer_user_id'],17)
        self.cur.execute('DELETE FROM users WHERE id=17')
        self.admin.commit()
        identity=self.identity()
        self.assertEqual(identity['reviewer'],'质安部 · 复核人员')
        self.assertIsNone(identity['reviewer_user_id'])

    def test_resubmission_clears_actor_and_new_round_never_uses_previous_department(self):
        self.assertEqual(self.submit()[1],200)
        self.cur.execute("UPDATE issues SET review_at=NULL,review_result=NULL,status='待复核'")
        self.admin.commit()
        self.assertEqual(self.identity()['reviewer'],'')
        self.cur.execute("UPDATE users SET role='supervisor_manager',real_name='新复核人' WHERE id=17")
        self.admin.commit()
        self.assertEqual(self.submit()[1],200)
        self.assertEqual(self.identity()['reviewer'],'督导中心 · 新复核人')
        self.cur.execute("SELECT count(*) AS n FROM inspection_issue_flow_history WHERE action_type='review_submitted'")
        self.assertEqual(self.cur.fetchone()['n'],2)

    def test_missing_or_different_round_evidence_is_never_guessed(self):
        self.cur.execute("UPDATE issues SET review_result='整改通过',review_at='2026-10-01 12:00:00'")
        self.cur.execute("""INSERT INTO inspection_issue_flow_history(issue_id,round_no,action_type,actor_name,actor_role,created_at)
            VALUES(42,1,'review_submitted','之前人员','supervisor','2026-09-01 04:00:00+00')""")
        self.assertEqual(self.identity()['reviewer'],'历史未记录')
        self.cur.execute("""INSERT INTO inspection_issue_flow_history(issue_id,round_no,action_type,created_at)
            VALUES(42,2,'review_submitted','2026-10-01 04:00:00+00')""")
        self.assertEqual(self.identity()['reviewer'],'历史未记录')

    def test_history_write_failure_rolls_back_review_and_actor_together(self):
        with patch.object(api,'record_issue_workflow_event',side_effect=RuntimeError('fixture failure')):
            self.assertEqual(self.submit()[1],500)
        identity=self.identity()
        self.assertIsNone(identity['review_result'])
        self.assertEqual(identity['reviewer'],'')
