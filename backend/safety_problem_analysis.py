"""Chapter-three statistics, bounded to the fixed evidence categories in the snapshot."""

from safety_report_data import ONSITE_PAGES, VIDEO_PAGES, category_rows, distribution
from safety_report_phrases import attach_phrases


def category_label(mode, name):
    label = name.removesuffix("类问题").removesuffix("类")
    if mode == "video" and label == "设备维修作业":
        label = "设备检维修作业"
    return label + "类问题"


def problem_analysis(report, mode):
    issues = report.get("safety_issues") or []
    if any('analysis_phrase' not in row for row in issues):
        issues = attach_phrases(issues, report.get('safety_phrases') or [], report.get('safety_settings'))
    analyses = report.get("safety_analysis") or {}
    categories = ONSITE_PAGES if mode == "onsite" else VIDEO_PAGES
    ranked = []
    for index, entry in enumerate(categories):
        name = entry[0]
        selected = category_rows(issues, mode, name)
        if selected:
            ranked.append((len(selected), index, name, selected))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    blocks = []
    for count, _, name, selected in ranked[: 1 if mode == "onsite" else 2]:
        analysis = analyses.get(mode + ":" + name) or {}
        eligible = {row["issue_id"] for row in selected}
        rows = distribution(selected, 'analysis_phrase')
        label = category_label(mode, name)
        blocks.append(
            {
                "name": name,
                "label": label,
                "count": count,
                "issue_ids": sorted(eligible),
                "distribution": rows,
                "chart_rows": rows[:6],
                "omitted_count": sum(r['count'] for r in rows[6:]),
                "chart_title": label + "分布",
                "causes": analysis.get("causes") or [],
            }
        )
    # Keep up to three scoped reasons, taking turns between the selected video categories.
    causes = []
    for index in range(max((len(block["causes"]) for block in blocks), default=0)):
        for block in blocks:
            if index < len(block["causes"]):
                reason = block["causes"][index].strip().rstrip("。.;；")
                if reason and reason not in causes:
                    causes.append(reason)
    heading = "占比较高问题分析"
    if blocks:
        heading += (
            "（"
            + "、".join(
                (
                    f"{b['label'].removesuffix('问题')}{b['count']}项问题"
                    if mode == "onsite"
                    else f"{b['label']}{b['count']}项"
                )
                for b in blocks
            )
            + "）"
        )
    texts = []
    for block in blocks:
        details = "、".join(
            f"{row['name']}（{row['count']}项）" for row in block["distribution"][:2]
        )
        texts.append(
            f"{block['label']}主要集中在{details}"
            if details
            else f"{block['label']}暂无统计数据"
        )
    narrative = (
        "问题分布：如右图所示，" + "；".join(texts) + "。"
        if texts
        else "问题分布：当前范围暂无可分析的固定类别问题。"
    )
    return {
        "mode": mode,
        "heading": heading,
        "narrative": narrative,
        "blocks": blocks,
        "causes": causes[:3],
    }
