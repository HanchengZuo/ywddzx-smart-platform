import os
import unittest
from inspection_record_grouping import monthly_record_cte, monthly_record_page_cte


@unittest.skipUnless(os.getenv('ISSUE_LIFECYCLE_DB_TEST') == '1', 'local database opt-in')
class MonthlyGroupingTests(unittest.TestCase):
    def test_group_pagination_preserves_scope_and_month_boundaries(self):
        import app
        conn = app.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                CREATE TEMP TABLE inspections(id INT, station_id INT, inspection_table_id INT, inspection_date DATE);
                CREATE TEMP TABLE stations(id INT);
                CREATE TEMP TABLE inspection_tables(id INT);
                INSERT INTO stations VALUES(1),(2);
                INSERT INTO inspection_tables VALUES(1),(2),(3);
                INSERT INTO inspections VALUES
                (1,1,1,'2026-09-30'),(2,1,2,'2026-09-01'),
                (3,2,1,'2026-09-29'),(4,1,1,'2026-08-31'),
                (5,1,3,'2026-09-15'),(6,1,1,'2025-09-01');
            ''')
            # Excluded tables must not re-enter through the selected monthly group.
            where = 'WHERE ins.inspection_table_id = ANY(%s)'
            cur.execute(f'WITH {monthly_record_cte(where)} SELECT COUNT(*) AS total FROM monthly_groups', ([1,2],))
            self.assertEqual(cur.fetchone()['total'], 4)
            pages = []
            for offset in range(4):
                cur.execute(f'WITH {monthly_record_page_cte(where)} SELECT id FROM filtered_ids ORDER BY id', ([1,2],1,offset))
                pages.append([row['id'] for row in cur.fetchall()])
            self.assertEqual(pages, [[1,2],[3],[4],[6]])
            cur.execute(f'WITH {monthly_record_page_cte(where + " AND ins.station_id = %s")} SELECT id FROM filtered_ids ORDER BY id', ([1,2],2,1,0))
            self.assertEqual([row['id'] for row in cur.fetchall()], [3])
        finally:
            conn.rollback()
            cur.close()
            conn.close()
