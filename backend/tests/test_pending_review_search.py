import os
import unittest

from issue_description_filter import IssueDescriptionFilterError
from pending_review_search import pending_review_keyword_clause


class PendingReviewKeywordTests(unittest.TestCase):
    def test_empty_search_adds_no_predicate(self):
        for value in (None, '', '  ', ',，；、'):
            self.assertEqual(pending_review_keyword_clause(value), ('', []))

    def test_words_are_parameterized_literal_matches_across_fields(self):
        clause, params = pending_review_keyword_clause("50% A_B C!D 'OR")
        self.assertEqual(params, ['%50!%%'] * 2 + ['%A!_B%'] * 2 + ['%C!!D%'] * 2 + ["%'OR%"] * 2)
        self.assertEqual(clause.count('%s'), len(params))
        self.assertNotIn('50%', clause)
        self.assertNotIn("'OR", clause)
        self.assertIn('i.standard_detail_text', clause)
        self.assertIn('i.internal_standard_detail_text', clause)
        self.assertIn('i.description', clause)
        self.assertIn('i.rectification_note', clause)
        self.assertIn('i.review_note', clause)
        self.assertIn('keyword_tag.tag_name', clause)
        self.assertNotIn('photo_path', clause)

    def test_case_insensitive_duplicates_and_limits(self):
        clause, params = pending_review_keyword_clause(' ETC,etc，接地 接地 ')
        self.assertEqual(params, ['%ETC%', '%ETC%', '%接地%', '%接地%'])
        self.assertEqual(clause.count(' OR EXISTS'), 2)
        for value in ('词' * 1001, ' '.join(f'词{i}' for i in range(21))):
            with self.assertRaisesRegex(IssueDescriptionFilterError, '关键词搜索'):
                pending_review_keyword_clause(value)

    @unittest.skipUnless(os.environ.get('ISSUE_LIFECYCLE_DB_TEST') == '1', 'Requires isolated PostgreSQL; temporary tables only')
    def test_real_postgres_search_combines_queue_facets_and_pagination(self):
        self.assertTrue(os.environ.get('DB_NAME', '').startswith('test_'), 'Use an isolated test database')
        import app as api
        conn = api.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                CREATE TEMP TABLE inspections (id int, inspector_id int);
                CREATE TEMP TABLE stations (id int, region text, station_name text, station_manager_name text);
                CREATE TEMP TABLE users (id int, real_name text);
                CREATE TEMP TABLE inspection_tables (id int, table_name text);
                CREATE TEMP TABLE inspection_internal_standards (id int, internal_standard_id text);
                CREATE TEMP TABLE inspection_internal_standard_links (internal_standard_id int, external_inspection_table_id int, external_standard_id text);
                CREATE TEMP TABLE inspection_internal_standard_tag_groups (id int, group_name text);
                CREATE TEMP TABLE inspection_internal_standard_tags (id int, group_id int, tag_name text);
                CREATE TEMP TABLE inspection_internal_standard_tag_links (internal_standard_id int, tag_id int);
                CREATE TEMP TABLE issues (id int, inspection_id int DEFAULT 1, station_id int DEFAULT 1,
                    inspection_table_id int DEFAULT 1, inspector_id int DEFAULT 1,
                    status text DEFAULT '待复核', audit_status text DEFAULT 'approved',
                    created_at timestamp DEFAULT '2026-09-05 12:30', standard_id text, internal_standard_id text,
                    standard_detail_text text, internal_standard_detail_text text, description text,
                    rectification_result text, rectification_note text, rectification_at timestamp,
                    review_result text, review_note text, review_at timestamp);
                INSERT INTO inspections VALUES (1,1);
                INSERT INTO stations VALUES (1,'浦东','甲站','王经理'),(2,'松金','乙站','李经理');
                INSERT INTO users VALUES (1,'张检查人');
                INSERT INTO inspection_tables VALUES (1,'设备设施现场表');
                INSERT INTO inspection_internal_standards VALUES (1,'I1');
                INSERT INTO inspection_internal_standard_links VALUES (1,1,'9001');
                INSERT INTO inspection_internal_standard_tag_groups VALUES (1,'区域');
                INSERT INTO inspection_internal_standard_tags VALUES (1,1,'加油区');
                INSERT INTO inspection_internal_standard_tag_links VALUES (1,1);
                INSERT INTO issues (id,standard_id,internal_standard_id,standard_detail_text,internal_standard_detail_text,
                    description,rectification_result,rectification_note,rectification_at,review_note) VALUES
                    (1,'9000','i1','设备接地','静电规范','锈蚀','已整改','复紧螺丝','2026-10-01','历史复核意见');
                INSERT INTO issues (id,station_id,description) VALUES (2,2,'ETC 50% A_B C!D');
                INSERT INTO issues (id,status,description) VALUES (3,'已闭环','接地 锈蚀');
                INSERT INTO issues (id,audit_status,description) VALUES (4,'rejected','接地 锈蚀');
                INSERT INTO issues (id) VALUES (5);
                INSERT INTO issues (id,review_result) VALUES (6,'已整改');
                INSERT INTO issues (id,description) SELECT 100+n,'跨页命中' FROM generate_series(1,21) n;
            ''')

            def ids(keyword, **facets):
                where, params = api.build_pending_review_filters({'keyword': keyword, **facets})
                cur.execute(f'SELECT i.id {api.PENDING_REVIEW_JOINS} {where} ORDER BY i.id', params)
                return [row['id'] for row in cur.fetchall()]

            for keyword in ('接地 锈蚀', '静电 锈蚀', '复紧螺丝', '历史复核意见', '区域：加油区', '外部规范ID：9001'):
                with self.subTest(keyword=keyword):
                    self.assertEqual(ids(keyword), [1])
            for keyword in ('50%', 'A_B', 'c!d', 'etc'):
                self.assertEqual(ids(keyword), [2])
            self.assertEqual(ids('整改通过'), [6])
            self.assertEqual(ids('王经理 设备设施现场表 接地'), [1])
            self.assertEqual(ids('2026-10-01'), [1])
            self.assertEqual(ids("' OR TRUE --"), [])
            self.assertEqual(ids('接地', stations='["乙站"]'), [])
            self.assertEqual(ids('接地', stations='["甲站"]', inspection_tables='["设备设施现场表"]'), [1])
            self.assertEqual(ids('接地', inspection_tables='["其他表"]'), [])
            where, params = api.build_pending_review_filters({'keyword': '跨页命中'})
            cur.execute(f'SELECT COUNT(*) AS total {api.PENDING_REVIEW_JOINS} {where}', params)
            self.assertEqual(cur.fetchone()['total'], 21)
            cur.execute(f'SELECT i.id {api.PENDING_REVIEW_JOINS} {where} ORDER BY i.id DESC LIMIT %s OFFSET %s', [*params, 5, 5])
            self.assertEqual([row['id'] for row in cur.fetchall()], [116,115,114,113,112])
        finally:
            conn.rollback()
            cur.close()
            conn.close()
