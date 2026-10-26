"""Literal keyword search within the existing pending-review queue."""

from issue_description_filter import IssueDescriptionFilterError, parse_description_keywords


ISSUE_SEARCH_TEXT = """CONCAT_WS(' ',
    i.id::text, TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI'),
    s.region, s.station_name, s.station_manager_name, issue_inspector.real_name,
    t.table_name, i.standard_id::text, i.internal_standard_id,
    i.standard_detail_text, i.internal_standard_detail_text, i.description,
    i.rectification_result, i.rectification_note, TO_CHAR(i.rectification_at, 'YYYY-MM-DD HH24:MI'),
    CASE WHEN i.review_result = '已整改' THEN '整改通过' ELSE i.review_result END,
    i.review_note, TO_CHAR(i.review_at, 'YYYY-MM-DD HH24:MI'), i.status,
    CASE COALESCE(i.audit_status, 'pending')
        WHEN 'approved' THEN '审核通过' WHEN 'rejected' THEN '审核否决' ELSE '待审核' END
)"""

TAG_SEARCH = """EXISTS (
    SELECT 1 FROM inspection_internal_standards keyword_standard
    LEFT JOIN inspection_internal_standard_links keyword_link
      ON keyword_link.internal_standard_id = keyword_standard.id
    LEFT JOIN inspection_tables keyword_table
      ON keyword_table.id = keyword_link.external_inspection_table_id
    LEFT JOIN inspection_internal_standard_tag_links keyword_tag_link
      ON keyword_tag_link.internal_standard_id = keyword_standard.id
    LEFT JOIN inspection_internal_standard_tags keyword_tag
      ON keyword_tag.id = keyword_tag_link.tag_id
    LEFT JOIN inspection_internal_standard_tag_groups keyword_group
      ON keyword_group.id = keyword_tag.group_id
    WHERE UPPER(keyword_standard.internal_standard_id) = UPPER(COALESCE(i.internal_standard_id, ''))
      AND CONCAT_WS(' ', CONCAT(keyword_group.group_name, '：', keyword_tag.tag_name),
          CONCAT('检查表：', keyword_table.table_name),
          CONCAT('外部规范ID：', keyword_link.external_standard_id::text)) ILIKE %s ESCAPE '!'
)"""


def pending_review_keyword_clause(value):
    try:
        keywords = parse_description_keywords(value)
    except IssueDescriptionFilterError as exc:
        raise IssueDescriptionFilterError(str(exc).replace('问题描述搜索', '关键词搜索')) from exc
    if not keywords:
        return '', []
    clauses, params = [], []
    # Each word may match a different field; all words must be present in the same issue.
    for word in keywords:
        pattern = '%' + word.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
        clauses.append(f"({ISSUE_SEARCH_TEXT} ILIKE %s ESCAPE '!' OR {TAG_SEARCH})")
        params.extend([pattern, pattern])
    return '(' + ' AND '.join(clauses) + ')', params
