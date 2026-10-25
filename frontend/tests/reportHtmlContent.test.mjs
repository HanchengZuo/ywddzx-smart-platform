import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileStyle } from '@vue/compiler-sfc'
import { buildReportHtmlSections } from '../src/utils/reportHtmlContent.js'

test('quality HTML preserves all saved slide content, blank percentages, zero values and merged totals', () => {
  const report = {
    slides: [
      { kind: 'cover', title: '封面' },
      { kind: 'agenda' },
      {
        kind: 'overall',
        title: '总体情况',
        narrative: '旧备用文字，不应代替实际PPT正文',
        narrative_runs: [{ text: '已保存的' }, { text: '总体情况' }],
        rows: [{ sequence: 1, unit_name: '浦东', total_issue_count: 0 }],
        total_row: { sequence: '合计', unit_name: '合计', total_issue_count: 0 },
      },
      {
        kind: 'finding_overview',
        text_blocks: [{ runs: [{ text: '油站环节' }, { text: '8项' }] }],
        text_lines: ['不要重复'],
        rows: [{ count: 0, percentage: '' }],
      },
      {
        kind: 'prohibited',
        subtitle: '禁止项',
        rows: [{ sequence: 7, description: '第七项', penalty: '' }],
      },
      { kind: 'flow_chart', distribution: [{ name: '器具管理', count: 0, percentage: 0 }] },
      {
        kind: 'issue_pairs',
        issues: [
          { issue_id: 9, station_name: '国郃', description: '原始问题', issue_photo: 'image.png' },
        ],
      },
      {
        kind: 'management_trace',
        typical_issue: { issue_id: 10, description: '典型问题' },
        analysis_items: [{ label: '监督层面', content: '原分析' }],
      },
      {
        kind: 'trace_analysis',
        conclusion: '原结论',
        improvement_measures: [{ level: '执行层面', content: '原措施' }],
      },
      { kind: 'work_plan', items: [{ title: '原计划', content: '计划内容' }] },
      { kind: 'ending' },
    ],
  }
  const original = JSON.stringify(report),
    sections = buildReportHtmlSections(report, 'quality_measurement')
  assert.equal(sections.length, 8)
  assert.deepEqual(sections[0].paragraphs, ['已保存的总体情况'])
  assert.equal(sections[0].tables[0].rows[0].at(-1), 0)
  assert.deepEqual(sections[0].tables[0].rows[1][0], { text: '合计', colspan: 2 })
  assert.deepEqual(sections[1].paragraphs, ['油站环节8项'])
  assert.deepEqual(sections[1].tables[0].rows[0].slice(-2), [0, ''])
  assert.equal(sections[2].tables[0].rows[0][0], 7)
  assert.deepEqual(sections[3].tables[0].rows[0], ['器具管理', 0, '0%'])
  assert.equal(sections[4].issues[0].issue_photo, 'image.png')
  assert.equal(sections[5].items[0].content, '原分析')
  assert.equal(sections[6].items[0].title, '执行层面')
  assert.equal(sections[7].items[0].content, '计划内容')
  assert.equal(JSON.stringify(report), original)
})

test('non-oil HTML uses saved periods, business order, classifications, evidence and analysis without reselecting', () => {
  const report = {
    period_text: '2026年10月1日至21日',
    scope_text: '已保存范围',
    issue_overview_text: '原问题概况',
    previous_month_rectification: {
      narrative: '9月已保存整改统计',
      units: [
        {
          unit_name: '浦东',
          total_count: 7,
          pending_acceptance_count: 2,
          pending_rectification_count: 0,
        },
      ],
    },
    units: ['浦东', '闵普徐'].map((name) => ({
      unit_name: name,
      station_count: 1,
      issue_count: 2,
      average_issue_count: 2,
      station_issue_rows: [{ station_name: '示例站', issue_count: 2 }],
      category_distribution: [{ name: '商品摆放', count: 2, percentage: 100 }],
    })),
    category_distribution: [{ name: '商品摆放', count: 2, percentage: 100 }],
    key_issue_summary: {
      selected_count: 1,
      percentage_of_all: 50,
      details: [
        {
          name: '重点商品',
          count: 1,
          issues: [{ issue_id: 123, description: '已保存重点商品问题' }],
          relationship: [{ name: '商品摆放', count: 1, percentage: 100 }],
        },
      ],
    },
    category_details: [
      {
        name: '商品摆放',
        features: [{ name: '价签', count: 2, example: '已保存示例' }],
        issues: [{ issue_id: 124, description: '已保存问题' }],
      },
    ],
    deep_analysis: {
      unit_highlights: [{ unit_name: '浦东', summary: '原AI分析' }],
      analysis_method: [{ title: '定量评估', content: '既有方法' }],
      core_findings: [{ title: '核心发现', content: '原结论' }],
    },
  }
  const sections = buildReportHtmlSections(report, 'non_oil')
  assert.deepEqual(sections[0].paragraphs, ['9月已保存整改统计'])
  assert.equal(sections[0].tables[0].rows[0][3], 0)
  assert.deepEqual(sections[1].paragraphs, [
    report.period_text,
    report.scope_text,
  ])
  assert.equal(sections[1].notes[0].content, report.issue_overview_text)
  assert.deepEqual(
    sections[1].tables[0].rows.map((row) => row[0]),
    ['浦东', '闵普徐'],
  )
  assert.equal(sections[1].tables[0].rows[0].at(-1), '示例站（2）')
  assert.equal(sections[3].paragraphs[0], '原AI分析')
  const key = sections.find((section) => section.title === '三、重点问题分析')
  assert.deepEqual(key.tables[0].rows, [[1, '50%']])
  assert.equal(key.items[0].content, '既有方法')
  assert.equal(
    sections.find((section) => section.title === '重点问题 · 重点商品').issues[0].issue_id,
    123,
  )
  assert.equal(sections.at(-1).items[0].content, '原结论')
})

test('legacy empty snapshots do not invent rows, percentages, issue references or generated content', () => {
  assert.equal(
    buildReportHtmlSections({ overview_text: '原概况' }, 'quality_measurement')[0].paragraphs[0],
    '原概况',
  )
  for (const type of ['quality_measurement', 'non_oil']) {
    const sections = buildReportHtmlSections({ slides: null, units: null, deep_analysis: {} }, type)
    assert.equal(sections.flatMap((section) => section.issues).length, 0)
    assert.equal(
      sections.flatMap((section) => section.tables).flatMap((table) => table.rows).length,
      0,
    )
  }
})

test('HTML content compiles as safe text with local reading navigation and shared photo events, never AI or raw HTML', () => {
  const source = readFileSync(
    new URL('../src/components/ReportHtmlContent.vue', import.meta.url),
    'utf8',
  )
  const { descriptor } = parse(source)
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'html-report', inlineTemplate: true }))
  assert.deepEqual(
    compileStyle({ source: descriptor.styles[0].content, scoped: true, id: 'html-report' }).errors,
    [],
  )
  assert.doesNotMatch(source, /v-html|axios|fetch\(|startGeneration/)
  assert.match(source, /\$emit\('photo', issue\)/)
  assert.match(source, /loading="lazy"/)
})

test('workspace reading colors meet normal-text contrast on their actual solid and gradient endpoints', () => {
  const css = readFileSync(new URL('../src/styles/reportStudio.css', import.meta.url), 'utf8')
  const luminance = (hex) =>
    hex
      .match(/\w\w/g)
      .map((channel) => {
        const value = parseInt(channel, 16) / 255
        return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
      })
      .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
  for (const [foreground, background] of [
    ['40566b', 'ffffff'],
    ['17344d', 'ffffff'],
    ['ffffff', '1c5878'],
    ['dfedf6', '164d6b'],
    ['276453', 'ffffff'],
  ]) {
    assert.ok(css.includes('#' + foreground) && css.includes('#' + background))
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a)
    assert.ok((values[0] + 0.05) / (values[1] + 0.05) >= 4.5)
  }
})
