import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  answerText,
  citedSources,
  conversationId,
  groupConversations,
  isExpertPending,
  scopeSummary,
} from '../src/utils/expertConversation.js'

test('thread grouping preserves legacy questions, separates conversations and searches follow-ups', () => {
  const items = [
    {
      id: 'b',
      question: '如何整改',
      created_at: '2026-10-17 12:00',
      status: 'answering',
      options: { conversation_id: 'a', conversation_title: '铅封规范' },
    },
    { id: 'legacy', question: '旧版独立问题', created_at: '2026-10-16', status: 'completed' },
    {
      id: 'a',
      question: '铅封规范',
      created_at: '2026-10-17 11:00',
      status: 'completed',
      options: { conversation_id: 'a' },
    },
  ]
  const before = JSON.stringify(items)
  const groups = groupConversations(items)
  assert.equal(groups.length, 2)
  assert.equal(groups[0].id, 'a')
  assert.equal(groups[0].title, '铅封规范')
  assert.equal(groups[0].running, true)
  assert.equal(groupConversations(items, '整改')[0].id, 'a')
  assert.equal(conversationId(items[1]), 'legacy')
  assert.equal(JSON.stringify(items), before)
})

test('copy includes only cited evidence and plain text, suggestions do not become citations', () => {
  const item = {
    question: '规范要求',
    result: {
      answer: {
        paragraphs: [{ title: '结论', text: '<b>仅作为文本</b>', sources: ['S1', 'S1'] }],
        caveat: '请核查',
      },
      sources: [
        { id: 'S1', title: '规范原文', kind: '外部规范' },
        { id: 'S2', title: '未引用资料', kind: '问题' },
      ],
    },
  }
  assert.deepEqual(
    citedSources(item.result).map((source) => source.id),
    ['S1'],
  )
  assert.ok(answerText(item).includes('结论\n<b>仅作为文本</b>'))
  assert.ok(answerText(item).includes('规范原文'))
  assert.ok(!answerText(item).includes('未引用资料'))
  assert.equal(answerText({}), '')
})

test('recognized scope is informational rather than mandatory and empty means full corpus', () => {
  assert.equal(scopeSummary(), '')
  assert.equal(
    scopeSummary({ date_from: '2026-07-01', date_to: '2026-07-31', station_names: ['国郃'] }),
    '2026-07-01 至 2026-07-31 · 国郃',
  )
  assert.equal(isExpertPending('answering'), true)
  assert.equal(isExpertPending('failed'), false)
})

test('expert sends no legacy range filters, summaries load separately and changing views guards stale responses', () => {
  const view = readFileSync(
    new URL('../src/views/operations/ExpertQaView.vue', import.meta.url),
    'utf8',
  )
  assert.ok(!view.includes('type="date"'))
  assert.ok(!view.includes('v-model.trim="options.region"'))
  assert.ok(!view.includes('allHistory'))
  assert.match(view, /params: \{ summary: '1' \}/)
  assert.match(view, /params: \{ conversation_id: id \}/)
  assert.match(view, /version !== readVersion/)
  assert.match(view, /const sourceConversation = activeConversation.value/)
  assert.match(view, /\{ question: text, parent_id: parentId.value \}/)
  assert.ok(!view.includes('v-html'))
})
