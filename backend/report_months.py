"""Lightweight month catalog for department report readers."""
import re


def valid_report_month(value):
    return bool(re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])", str(value or "")))


def list_report_months(cur, report_type, is_current):
    # Read only metadata, not every historical report's potentially large JSON payload.
    cur.execute(
        """
        SELECT id, report_month,
               report_payload ->> 'month' AS payload_month,
               report_payload ->> 'data_policy_version' AS data_policy_version
        FROM inspection_report_snapshots
        WHERE report_type = %s
          AND jsonb_typeof(report_payload) = 'object'
        ORDER BY generated_at DESC, id DESC;
        """,
        (report_type,),
    )
    months = {}
    for row in cur.fetchall():
        month = row.get('report_month')
        if (month in months or not valid_report_month(month)
                or not valid_report_month(row.get('payload_month'))
                or not is_current(report_type, {'data_policy_version': row.get('data_policy_version')})):
            continue
        months[month] = {'month': month, 'snapshot_id': int(row['id'])}
    return list(months.values())
