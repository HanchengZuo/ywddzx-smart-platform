import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import {
  parseDescriptionKeywords,
  descriptionFilterError,
} from '../src/utils/issueDescriptionFilter.js'
import { buildFilterSummary } from '../src/utils/filterSummary.js'

test('description keywords accept Chinese separators, whitespace and deduplicate', () => {
  assert.deepEqual(parseDescriptionKeywords(' 接地,锈蚀，接地;破损；损坏、ETC\nEtc\t油品 '), [
    '接地',
    '锈蚀',
    '破损',
    '损坏',
    'ETC',
    '油品',
  ])
  assert.deepEqual(parseDescriptionKeywords(' ,，;；、\n '), [])
  assert.deepEqual(parseDescriptionKeywords('50% A_B C!D'), ['50%', 'A_B', 'C!D'])
  assert.deepEqual(parseDescriptionKeywords('铅封'), ['铅封'])
})

test('validation bounds distinct keywords and Unicode length without truncation', () => {
  assert.equal(descriptionFilterError(Array.from({ length: 20 }, (_, i) => `词${i}`).join(' ')), '')
  assert.match(
    descriptionFilterError(Array.from({ length: 21 }, (_, i) => `词${i}`).join(' ')),
    /20/,
  )
  assert.equal(descriptionFilterError('接地 '.repeat(100)), '')
  assert.equal(descriptionFilterError('😀'.repeat(1000)), '')
  assert.match(descriptionFilterError('😀'.repeat(1001)), /1000/)
})

test('description summary preserves the original input and pending state', () => {
  const definitions = [['issueDescription', '问题描述']]
  const applied = { issueDescription: '接地 锈蚀' }
  const draft = { issueDescription: '接地，破损' }
  const summary = buildFilterSummary(definitions, draft, applied)[0]
  assert.equal(summary.value, '接地，破损')
  assert.equal(summary.applied, '接地 锈蚀')
  assert.equal(summary.state, 'pending')
  assert.equal(buildFilterSummary(definitions, draft)[0].state, 'set')
  assert.equal(buildFilterSummary(definitions, { issueDescription: '' })[0].state, 'empty')
  assert.equal(
    buildFilterSummary(definitions, { issueDescription: '' }, applied)[0].state,
    'pending',
  )
  assert.equal(buildFilterSummary(definitions, { issueDescription: '铅封' })[0].value, '铅封')
})

test('description filter remains one original-sized input with a placeholder only', () => {
  const filename = new URL('../src/views/inspection/IssuesView.vue', import.meta.url)
  const source = readFileSync(filename, 'utf8')
  assert.match(source, /<div class="filter-item" :data-filter-state="filterFieldState\('issueDescription'\)">\s*<label>问题描述<\/label>\s*<input v-model.trim="filters.issueDescription" placeholder="如：接地 锈蚀（空格分隔多个关键词）" \/>/)
  assert.doesNotMatch(source, /IssueDescriptionFilter|descriptionMatch|description_match|description-keyword/)
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const result = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'description-filter-test' })
  assert.deepEqual(result.errors, [])
})
