import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { taskProgressGroups, inboxMetrics } from '../src/utils/inspectionTaskProgress.js'
const source = readFileSync(
  new URL('../src/components/ScheduleTaskInbox.vue', import.meta.url),
  'utf8',
)
const ref = (value = null) => ({ value })

test('a notification opens only the visible header inbox, not both desktop and mobile instances', () => {
  const code = source.match(/function openFromNotification\(\) \{[\s\S]*?\n\}/)[0]
  let opens = 0
  const context = vm.createContext({
    trigger: ref({ getClientRects: () => [] }),
    open: () => {
      opens++
    },
  })
  vm.runInContext(code + ';openFromNotification()', context)
  assert.equal(opens, 0)
  context.trigger.value = { getClientRects: () => [{}] }
  vm.runInContext('openFromNotification()', context)
  assert.equal(opens, 1)
})

test('station progress includes completed sibling tables and separates dates and field/video tasks', () => {
  const data = [
    { id: 1, station_id: 1, mode: 'offline', scheduled_date: '2026-10-22', status: 'completed' },
    { id: 2, station_id: 1, mode: 'offline', scheduled_date: '2026-10-22', status: 'pending' },
    { id: 3, station_id: 1, mode: 'online', scheduled_date: '2026-10-22', status: 'completed' },
    { id: 4, station_id: 1, mode: 'offline', scheduled_date: '2026-10-21', status: 'pending' },
  ]
  const original = structuredClone(data),
    groups = taskProgressGroups(data)
  assert.deepEqual(
    groups.map((g) => [g.total, g.completed, g.pending, g.percent]),
    [
      [2, 1, 1, 50],
      [1, 1, 0, 100],
      [1, 0, 1, 0],
    ],
  )
  assert.deepEqual(data, original)
  assert.deepEqual(taskProgressGroups(), [])
})

test('today progress and two kinds of historical unfinished counts never mix', () => {
  const metrics = inboxMetrics({
    buckets: {
      today_offline: { total: 6, completed: 2, pending: 4 },
      today_online: { total: 3, completed: 1, pending: 2 },
      history_offline: { completed: 12, pending: 7 },
      history_online: { completed: 9, pending: 5 },
    },
  })
  assert.deepEqual(metrics, {
    todayCompleted: 3,
    todayTotal: 9,
    todayExempted: 0,
    todayPending: 6,
    historyOffline: 7,
    historyOnline: 5,
  })
  assert.equal(inboxMetrics().todayTotal, 0)
})

test('inbox requests a self-only server bucket and whole-station page, emitting global pending count', async () => {
  const calls = []
  const context = vm.createContext({
    disposed: false,
    loading: ref(false),
    dialog: { value: { open: true } },
    serial: 0,
    controller: undefined,
    AbortController,
    activeTab: ref('history_offline'),
    page: ref(2),
    pageSize: 24,
    tasks: ref([]),
    total: ref(0),
    today: ref(''),
    loadedAgenda: ref(),
    summary: ref(),
    totalGroups: ref(0),
    error: ref(''),
    emit: (...args) => calls.push(args),
    axios: {
      get: async (url, options) => {
        calls.push([url, options.params])
        return {
          data: {
            tasks: [
              { id: 8, status: 'completed' },
              { id: 9, status: 'pending' },
            ],
            count: 31,
            today: '2026-10-22',
            page: 2,
            total_groups: 30,
            buckets: { history_offline: { pending: 12 } },
          },
        }
      },
    },
  })
  vm.runInContext(
    source.slice(source.indexOf('async function load()'), source.indexOf('const polling =')),
    context,
  )
  await context.load()
  assert.equal(calls[0][0], '/api/my-schedule-tasks')
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0][1])), {
    bucket: 'history_offline',
    page: 2,
    page_size: 24,
  })
  assert.deepEqual(calls[1], ['count', 31])
  assert.equal(context.tasks.value.length, 2)
  assert.equal(context.totalGroups.value, 30)
})

test('switching categories cancels stale requests and resets pagination without changing others data', () => {
  let aborts = 0,
    loads = 0
  const context = vm.createContext({
    serial: 3,
    controller: { abort: () => aborts++ },
    loading: ref(true),
    activeTab: ref('all'),
    page: ref(3),
    tasks: ref([{ id: 1 }]),
    totalPages: ref(4),
    load: () => loads++,
    dialog: { value: { open: false } },
  })
  vm.runInContext(
    source.slice(source.indexOf('function changeView('), source.indexOf('function open()')),
    context,
  )
  context.chooseTab('history_offline')
  assert.equal(aborts, 1)
  assert.equal(loads, 1)
  assert.equal(context.page.value, 1)
  assert.equal(context.activeTab.value, 'history_offline')
  assert.equal(context.tasks.value.length, 0)
  context.goPage(2)
  assert.equal(context.page.value, 2)
  context.goPage(99)
  assert.equal(loads, 2)
})

test('progress UI compiles with explicit states, history field/video tabs and no manual completion', () => {
  const { descriptor } = parse(source)
  assert.ok(compileScript(descriptor, { id: 'inbox-progress-test' }).content)
  assert.deepEqual(
    compileTemplate({
      source: descriptor.template.content,
      filename: 'ScheduleTaskInbox.vue',
      id: 'inbox-progress-test',
    }).errors,
    [],
  )
  for (const style of descriptor.styles)
    assert.deepEqual(compileStyle({ source: style.content, id: 'inbox-progress-test' }).errors, [])
  assert.match(source, /历史现场未完成/)
  assert.match(source, /历史视频未完成/)
  assert.match(source, /role="progressbar"/)
  assert.match(source, /task.completion_inspection_id/)
  assert.match(source, /task.status === 'pending'/)
  assert.doesNotMatch(descriptor.template.content, /次日归档|核对完成情况|type="checkbox"/)
})
