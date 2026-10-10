import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileTemplate } from '@vue/compiler-sfc'
import {
  parseDescriptionKeywords,
  descriptionFilterError,
  describeDescriptionFilter,
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

test('filter summary tracks match mode only when there are keywords', () => {
  const definitions = [['issueDescription', '问题描述']]
  const applied = { issueDescription: '接地 锈蚀', descriptionMatch: 'all' }
  const draft = { ...applied, descriptionMatch: 'any' }
  const summary = buildFilterSummary(definitions, draft, applied)[0]
  assert.equal(summary.value, '任一包含：接地、锈蚀')
  assert.equal(summary.applied, '全部包含：接地、锈蚀')
  assert.equal(summary.state, 'pending')
  assert.equal(buildFilterSummary(definitions, draft)[0].state, 'set')
  assert.equal(
    buildFilterSummary(
      definitions,
      { issueDescription: '', descriptionMatch: 'any' },
      { issueDescription: '', descriptionMatch: 'all' },
    )[0].state,
    'empty',
  )
  assert.equal(
    buildFilterSummary(definitions, { issueDescription: '' }, applied)[0].state,
    'pending',
  )
  assert.equal(buildFilterSummary(definitions, { issueDescription: '铅封' })[0].value, '铅封')
  assert.equal(describeDescriptionFilter(applied), '全部包含：接地、锈蚀')
})

test('multi-keyword input and issues templates compile', () => {
  for (const path of ['components/IssueDescriptionFilter.vue', 'views/inspection/IssuesView.vue']) {
    const filename = new URL(`../src/${path}`, import.meta.url)
    const { descriptor, errors } = parse(readFileSync(filename, 'utf8'))
    assert.deepEqual(errors, [])
    const result = compileTemplate({
      source: descriptor.template.content,
      filename: filename.pathname,
      id: 'description-filter-test',
    })
    assert.deepEqual(result.errors, [])
  }
})
