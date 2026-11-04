import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { bucketCounts, filterPeople, overviewMetrics } from '../src/utils/scheduleTaskOverview.js'

const people = [
  { id: 1, name: '张岚', buckets: { today_online: { total: 3, completed: 0, pending: 0, exempted: 3 } } },
  { id: 2, name: '李宁', buckets: { today_offline: { total: 2, completed: 1, pending: 1 }, history_online: { total: 2, completed: 0, pending: 2 } } },
  { id: 3, name: '张静', buckets: {} },
]

test('today, history, exemptions and unassigned staff stay distinct', () => {
  assert.deepEqual(overviewMetrics(people), { people: 3, pendingPeople: 1, todayPending: 1,
    todayCompleted: 1, todayExempted: 3, historyPending: 2, historyOffline: 0, historyOnline: 2 })
  assert.deepEqual(bucketCounts(people[2]), { total: 0, pending: 0, completed: 0, exempted: 0 })
})

test('search and state are scoped to the selected bucket without mutating the roster', () => {
  const filter = (keyword, bucket, state) => filterPeople(people, { keyword, bucket, state }).map(person => person.id)
  assert.deepEqual(filter('', 'all', 'all'), [2, 1, 3])
  assert.deepEqual(filter('张', 'all', 'clear'), [1, 3])
  assert.deepEqual(filter('', 'today_online', 'pending'), [])
  assert.deepEqual(filter('', 'history_online', 'pending'), [2])
  assert.deepEqual(people.map(person => person.id), [1, 2, 3])
})

test('read-only overview renders and compiles with real bindings', () => {
  const filename = 'ScheduleTaskOverviewView.vue'
  const source = readFileSync(new URL('../src/views/inspection/' + filename, import.meta.url), 'utf8')
  const { descriptor, errors } = parse(source, { filename })
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: filename })
  const result = compileTemplate({ source: descriptor.template.content, filename, id: filename,
    compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.doesNotMatch(source, /axios\.(post|put|patch|delete)|v-html/)
})
