def monthly_record_cte(where_clause):
    """Group only records already admitted by permission and user filters."""
    return f"""
        matched_records AS (
            SELECT ins.id, ins.station_id, ins.inspection_date,
                   DATE_TRUNC('month', ins.inspection_date) AS record_month
            FROM inspections ins
            JOIN stations s ON ins.station_id = s.id
            JOIN inspection_tables t ON ins.inspection_table_id = t.id
            {where_clause}
        ),
        monthly_groups AS (
            SELECT station_id, record_month, MAX(inspection_date) AS latest_date,
                   MAX(id) AS latest_id
            FROM matched_records
            GROUP BY station_id, record_month
        )
    """


def monthly_record_page_cte(where_clause):
    return monthly_record_cte(where_clause) + """,
        selected_groups AS (
            SELECT station_id, record_month FROM monthly_groups
            ORDER BY latest_date DESC, latest_id DESC
            LIMIT %s OFFSET %s
        ),
        filtered_ids AS (
            SELECT record.id FROM matched_records record
            JOIN selected_groups selected
              ON record.station_id = selected.station_id
             AND record.record_month IS NOT DISTINCT FROM selected.record_month
        )
    """
