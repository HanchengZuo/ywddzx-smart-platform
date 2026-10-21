const list = (value) => (Array.isArray(value) ? value : [])
const text = (value) =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : ''
const paragraphs = (values) => values.map(text).filter((value) => value.trim())
const percent = (value) =>
  value === undefined || value === null || value === '' ? '' : `${text(value).replace(/%$/, '')}%`
const table = (headings, rows) => ({ headings, rows })
const distribution = (rows) =>
  table(
    ['问题类别', '问题数量', '占比'],
    list(rows).map((row) => [row.display_name || row.name, row.count, percent(row.percentage)]),
  )
const items = (rows) =>
  list(rows).map((row) =>
    typeof row === 'string'
      ? { title: '', content: row }
      : { title: row.title || row.label || row.level || '', content: text(row.content) },
  )
const overallTable = (rows) =>
  table(
    [
      '序号',
      '二级单位',
      '检查油库',
      '检查加油站',
      '检查运输车辆',
      '一般性问题',
      '违规违纪问题',
      '涉及禁止项问题',
      '问题总数',
    ],
    rows.map((row) => [
      ...(row.sequence === '合计' ? [{ text: '合计', colspan: 2 }] : [row.sequence, row.unit_name]),
      row.oil_depot_count,
      row.station_count,
      row.transport_vehicle_count,
      row.general_issue_count,
      row.violation_issue_count,
      row.prohibited_issue_count,
      row.total_issue_count,
    ]),
  )

// Project only saved report fields. Never mix unsaved configuration or live issue-library rows into a draft.
export function buildReportHtmlSections(report = {}, type) {
  const sections = type === 'quality_measurement' ? qualitySections(report) : nonOilSections(report)
  return sections.map((section, index) => ({
    paragraphs: [],
    tables: [],
    items: [],
    issues: [],
    ...section,
    id: `report-html-section-${index + 1}`,
  }))
}

function qualitySections(report) {
  const slides = list(report.slides).filter(
    (slide) => !['cover', 'agenda', 'ending'].includes(slide.kind),
  )
  if (!slides.length)
    return [
      {
        title: '总体情况',
        paragraphs: paragraphs([report.overview_text]),
        tables: [
          overallTable([
            ...list(report.rows),
            ...(report.total_row && Object.keys(report.total_row).length ? [report.total_row] : []),
          ]),
        ],
      },
    ]
  return slides.map((slide) => {
    const section = {
      title: [slide.title, slide.subtitle].filter(Boolean).join(' · ') || '检查情况',
      paragraphs: paragraphs([
        list(slide.narrative_runs).length
          ? list(slide.narrative_runs)
              .map((run) => text(run.text))
              .join('')
          : slide.narrative,
        slide.summary_text,
        slide.conclusion,
        ...(list(slide.text_blocks).length
          ? slide.text_blocks.map((block) =>
              list(block.runs)
                .map((run) => text(run.text))
                .join(''),
            )
          : list(slide.text_lines)),
      ]),
      tables: [],
      items: items([
        ...list(slide.analysis_items),
        ...list(slide.improvement_measures),
        ...list(slide.items),
      ]),
      issues: [...list(slide.issues), ...(slide.typical_issue ? [slide.typical_issue] : [])],
    }
    if (slide.kind === 'overall')
      section.tables.push(
        overallTable([
          ...list(slide.rows),
          ...(slide.total_row && Object.keys(slide.total_row).length ? [slide.total_row] : []),
        ]),
      )
    if (slide.kind === 'finding_overview')
      section.tables.push(
        table(
          ['序号', '环节', '问题类型', '问题数量', '占比/%'],
          list(slide.rows).map((row) => [
            row.sequence,
            row.section,
            row.problem_type,
            row.count,
            row.percentage,
          ]),
        ),
      )
    if (slide.kind === 'prohibited')
      section.tables.push(
        table(
          ['序号', '环节', '基层单位', '禁止项管理规定', '处罚情况'],
          list(slide.rows).map((row) => [
            row.sequence,
            row.section || '加油站环节',
            row.unit_name,
            row.description,
            row.penalty,
          ]),
        ),
      )
    if (slide.kind === 'flow_chart') section.tables.push(distribution(slide.distribution))
    return section
  })
}

function nonOilSections(report) {
  const previous = report.previous_month_rectification || {},
    analysis = report.deep_analysis || {},
    key = report.key_issue_summary || {}
  const sections = [
    {
      title: '一、总体情况概述',
      paragraphs: paragraphs([previous.narrative]),
      tables: [
        table(
          ['片区/单位', '全部问题', '待验收', '待整改'],
          list(previous.units).map((unit) => [
            unit.unit_name,
            unit.total_count,
            unit.pending_acceptance_count,
            unit.pending_rectification_count,
          ]),
        ),
      ],
    },
    {
      title: '巡检范围',
      paragraphs: paragraphs([report.period_text, report.scope_text, report.issue_overview_text]),
      tables: [
        table(
          ['片区/单位', '检查站数', '问题总数', '站均问题数', '加油站问题数'],
          list(report.units).map((unit) => [
            unit.unit_name,
            unit.station_count,
            unit.issue_count,
            unit.average_issue_count,
            list(unit.station_issue_rows)
              .map((station) => `${station.station_name}（${station.issue_count}）`)
              .join('、'),
          ]),
        ),
      ],
    },
    {
      title: '二、片区问题汇总 · 总体概况',
      paragraphs: paragraphs([report.unit_overview_text, report.category_distribution_text]),
      tables: [distribution(report.category_distribution)],
    },
  ]
  for (const unit of list(report.units)) {
    const highlight =
      list(analysis.unit_highlights).find((item) => item.unit_name === unit.unit_name) || {}
    sections.push({
      title: `片区问题汇总 · ${unit.unit_name}`,
      paragraphs: paragraphs([highlight.summary]),
      tables: [
        table(
          ['站点', '问题数量'],
          list(unit.station_issue_rows).map((row) => [row.station_name, row.issue_count]),
        ),
        distribution(unit.category_distribution),
      ],
      issues: list(highlight.highlighted_issues),
    })
  }
  sections.push({
    title: '三、重点问题分析',
    tables: [
      table(
        ['已纳入重点问题', '占全部问题比例'],
        key.selected_count != null || report.key_issue_count != null
          ? [
              [
                key.selected_count ?? report.key_issue_count,
                percent(key.percentage_of_all ?? report.key_issue_percentage),
              ],
            ]
          : [],
      ),
      distribution(key.distribution),
    ],
    items: items(analysis.analysis_method),
  })
  for (const group of list(key.details)) {
    if (!group.count && !list(group.issues).length) continue
    sections.push({
      title: `重点问题 · ${group.name}`,
      tables: [distribution(group.relationship)],
      issues: list(group.issues),
    })
  }
  for (const group of list(report.category_details)) {
    sections.push({
      title: `四、具体结果分析 · ${group.name}`,
      issues: list(group.issues),
      tables: [
        table(
          ['问题特征', '数量', '示例'],
          list(group.features).map((row) => [row.name, row.count, row.example]),
        ),
      ],
    })
  }
  if (!list(report.category_details).length) {
    for (const group of list(analysis.typical_issues))
      sections.push({
        title: group.title || group.category_name,
        paragraphs: paragraphs([group.summary]),
        issues: list(group.issues),
      })
  }
  for (const [key, title] of [
    ['core_findings', '五、检查结果分析 · 核心发现'],
    ['attribution_analysis', '归因分析'],
    ['improvement_suggestions', '改进建议'],
    ['action_priorities', '后续工作'],
  ]) {
    if (list(analysis[key]).length) sections.push({ title, items: items(analysis[key]) })
  }
  return sections
}
