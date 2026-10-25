const list = (value) => (Array.isArray(value) ? value : [])
const text = (value) =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : ''
const paragraphs = (values) => values.map(text).filter((value) => value.trim())
const percent = (value) =>
  value === undefined || value === null || value === '' ? '' : `${text(value).replace(/%$/, '')}%`
const table = (headings, rows) => ({ headings, rows })
const distribution = (rows) =>
  ({ ...table(
    ['问题类别', '问题数量', '占比'],
    list(rows).map((row) => [row.display_name || row.name, row.count, percent(row.percentage)]),
  ), chartRows: list(rows) })
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
  const sections = type === 'quality_measurement' ? qualitySections(report)
    : type === 'equipment_facilities' ? equipmentSections(report) : nonOilSections(report)
  return sections.map((section, index) => ({
    paragraphs: [],
    tables: [],
    items: [],
    issues: [],
    notes: [],
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
      paragraphs: paragraphs([report.period_text, report.scope_text]),
      notes: report.issue_overview_text ? [{ title: '完整问题概况', content: report.issue_overview_text }] : [],
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
      paragraphs: paragraphs([report.unit_overview_text]),
      tables: [{ ...distribution(report.category_distribution), title: '非油检查问题分布', description: report.category_distribution_text }],
    },
  ]
  for (const unit of list(report.units)) {
    const highlight =
      list(analysis.unit_highlights).find((item) => item.unit_name === unit.unit_name) || {}
    sections.push({
      title: `片区问题汇总 · ${unit.unit_name}`,
      collapsible: true,
      metrics: `${unit.station_count ?? 0}站 · ${unit.issue_count ?? 0}项问题`,
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
      tone: 'priority',
      tables: [distribution(group.relationship)],
      issues: list(group.issues),
    })
  }
  for (const group of list(report.category_details)) {
    sections.push({
      title: `四、具体结果分析 · ${group.name}`,
      collapsible: true,
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

const groundingIds = new Set([9000, 9001, 9002, 9003, 9006, 9007, 9008, 9009, 9010, 9018, 9022, 9023, 9025, 9026, 9029, 9030, 9031, 9032, 9039, 9044, 9047, 9048, 9057, 9058])
const unitKey = name => text(name).replace('闵浦徐', '闵普徐').replace(/管理片区|片区|公司/g, '')

export function equipmentPhraseDistribution(analysis) {
  if (!Array.isArray(analysis.issues)) return list(analysis.phrase_distribution)
  const counts = new Map()
  for (const issue of analysis.issues) {
    const name = groundingIds.has(Number(issue.external_standard_id)) ? '设备接地不规范' : issue.phrase || '未匹配检查短语'
    counts.set(name, (counts.get(name) || 0) + 1)
  }
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-CN'))
    .map(([name, count]) => ({ name, count, percentage: Number((count / analysis.issues.length * 100).toFixed(1)) }))
}

function equipmentSections(report) {
  const analysis = report.equipment_analysis || {}
  const issues = list(analysis.issues)
  const phrases = equipmentPhraseDistribution(analysis)
  const leading = phrases[0]
  const sections = [{
    title: '一、总体情况', paragraphs: paragraphs([report.overview_text, report.region_text]),
    tables: [table(['片区/单位', '检查站数', '问题总数', '站均问题数'], list(report.region_rows).map(row => [row.unit_name, row.station_count, row.issue_count, row.average_issue_count]))]
  }, {
    title: '二、问题数据统计分析',
    paragraphs: paragraphs([leading ? `${leading.name}是单类问题${phrases.filter(row => row.count === leading.count).length > 1 ? '并列' : ''}最多的项，共${leading.count}个问题，占比${leading.percentage}%。` : '本次报告未纳入设备设施问题。']),
    tables: [
      { ...distribution(report.area_distribution), title: '按所属区域分类' },
      { ...distribution(report.item_distribution), title: '按检查事项分类' },
      { ...distribution(phrases), title: '按检查内容短语分类' }
    ]
  }]
  for (const group of list(analysis.high_groups)) {
    const records = list(group.issues)
    sections.push({
      title: `高频问题 · ${group.phrase}`, collapsible: true, metrics: `${records.length}项`,
      items: [{ title: '问题产生原因', content: list(group.causes).join('；') }],
      tables: [table(['站点', '问题描述'], records.map(issue => [issue.station_name, issue.description]))],
      issues: [...records].sort((a, b) => Number(!a.issue_photo) - Number(!b.issue_photo) || a.issue_id - b.issue_id).slice(0, 2)
    })
  }
  const special = new Set(list(analysis.special_issue_ids).map(Number))
  for (const region of list(report.region_rows)) {
    const unitIssues = issues.filter(issue => unitKey(issue.management_unit) === unitKey(region.unit_name))
    const stations = list(report.station_ranking).filter(station => unitKey(station.management_unit) === unitKey(region.unit_name))
    const chosen = unitIssues.filter(issue => special.has(Number(issue.issue_id)))
    sections.push({
      title: `片区检查发现 · ${region.unit_name}`, collapsible: true,
      metrics: `${region.station_count ?? stations.length}站 · ${region.issue_count ?? unitIssues.length}项问题`,
      paragraphs: paragraphs([`检查站点：${stations.map(station => station.station_name).join('、') || '成稿未记录站名'}。`, ...chosen.map(issue => `特性问题 · ${issue.station_name}：${issue.description}`)]),
      tables: [table(['站点', '问题数量', '主要问题'], stations.map(station => {
        const stationIssues = unitIssues.filter(issue => issue.station_id === station.station_id)
        return [station.station_name, station.issue_count ?? stationIssues.length, stationIssues.map(issue => issue.description).join('\n') || '本次未发现参与报告的问题。']
      }))], issues: chosen
    })
  }
  const priorityIds = new Set(list(analysis.severe_issue_ids).map(Number))
  const priority = issues.filter(issue => priorityIds.has(Number(issue.issue_id)))
  if (priority.length) sections.push({ title: '重点问题', tone: 'priority', issues: priority })
  const deep = report.deep_analysis || {}
  if (list(deep.problem_analysis).length) sections.push({ title: '问题分析', items: items(deep.problem_analysis) })
  if (list(deep.work_suggestions).length) sections.push({ title: '工作建议', items: items(deep.work_suggestions) })
  return sections
}

export function reportReadingMetrics(report, type) {
  if (!['non_oil', 'equipment_facilities'].includes(type)) return []
  const summary = report.summary || {}
  const issueCount = summary.total_issue_count ?? summary.issue_count ?? (type === 'equipment_facilities' ? report.equipment_analysis?.issues?.length : undefined)
  const stations = summary.station_count ?? summary.inspected_station_count
  const units = type === 'non_oil' ? report.units : report.region_rows
  return [
    { label: '报告问题', value: issueCount, unit: '项' },
    { label: '受检站点', value: stations, unit: '站' },
    { label: '片区及单位', value: Array.isArray(units) ? units.length : undefined, unit: '个' },
    { label: type === 'non_oil' ? '重点问题' : '高频问题类别', value: type === 'non_oil' ? report.key_issue_summary?.selected_count ?? report.key_issue_count : report.equipment_analysis?.high_groups?.length, unit: type === 'non_oil' ? '项' : '类' }
  ].filter(item => item.value !== undefined && item.value !== null)
}
