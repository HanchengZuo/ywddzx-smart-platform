import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import { parse as parseJavascript } from '@babel/parser'

const source = file => readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
for (const file of ['App.vue', 'components/InspectionSchedulePanel.vue', 'components/DailyInspectionTeams.vue', 'components/AutomaticSchedule.vue', 'components/ScheduleTaskInbox.vue']) {
  test(`${file}: the actual inline compiled render function is valid JavaScript`, () => {
    const { descriptor } = parse(source(file))
    const result = compileScript(descriptor, { id: file, inlineTemplate: true })
    assert.doesNotThrow(() => parseJavascript(result.content, { sourceType: 'module' }))
  })
}

test('student drag submits server-owned student/leader IDs and refreshes only after confirmation', async () => {
  const calls = []
  const context = vm.createContext({
    draggingStudent: { value: 10 }, selectedStudent: { value: null }, editable: { value: true },
    preview: { value: null }, saving: { value: false }, error: { value: '' },
    context: { value: { day: '2026-10-20', revision: 4 } },
    displayGroups: { value: [{ name: '外勤甲组', members: [{ id: 10 }] }] },
    axios: { post: async (url, body) => { calls.push({url,body}); return {data: {day: '2026-10-20', revision: 5}} } },
    load: async () => calls.push('load'), emit: (...args) => calls.push(args),
    window: { dispatchEvent: () => calls.push('notify') }, Event: class {},
  })
  const script = source('components/DailyInspectionTeams.vue')
  vm.runInContext(script.slice(script.indexOf('async function dropStudent'), script.indexOf('let controller,')), context)
  await context.dropStudent({name: '外勤乙组', leader_id: 3})
  assert.equal(calls[0].body.student_id, 10)
  assert.equal(calls[0].body.leader_id, 3)
  assert.equal(calls[0].body.revision, 4)
  assert.equal(calls[1], 'load')
  assert.equal(calls[2][0], 'saved')
  assert.equal(calls[2][1].adjusted, true)
  assert.equal(context.saving.value, false)
  assert.equal(context.draggingStudent.value, null)
})

test('rejected student move never emits a successful save and retains the server error', async () => {
  const calls = []
  const context = vm.createContext({
    draggingStudent: {value: 10}, selectedStudent: {value: null}, editable: {value: true},
    preview: {value: null}, saving: {value: false}, error: {value: ''},
    context: {value: {day: '2026-10-20', revision: 1}},
    displayGroups: {value: [{name: '外勤甲组', members: [{id: 10}]}]},
    axios: {post: async () => { throw {response: {status: 409, data: {error: '已有站点派工'}}} }},
    load: async () => calls.push('reload'), emit: () => calls.push('saved'),
  })
  const script = source('components/DailyInspectionTeams.vue')
  vm.runInContext(script.slice(script.indexOf('async function dropStudent'), script.indexOf('let controller,')), context)
  await context.dropStudent({name: '内勤视频组', leader_id: null})
  assert.deepEqual(calls, ['reload'])
  assert.equal(context.error.value, '已有站点派工')
})

test('automatic dispatch uses the fixed origin and local route calculation without online geocoding or paid AI', () => {
  const script = source('components/AutomaticSchedule.vue')
  assert.match(script,/上海市浦东新区世纪大道1200号/)
  assert.doesNotMatch(script,/AMap|Geocoder|scheduleOrigin|originError|deepseek/i)
  assert.match(script,/offlineCount = ref\(2\)/)
  assert.match(script,/onlineCount = ref\(3\)/)
})

test('personal inbox lives in desktop and mobile headers, not the page body', () => {
  const app = source('App.vue')
  const main = app.slice(app.indexOf('<main class="content">'), app.indexOf('</main>'))
  assert.doesNotMatch(main, /ScheduleTaskInbox/)
  assert.equal((app.match(/<ScheduleTaskInbox /g) || []).length, 2)
  assert.match(app, /scheduleAgenda.value = payload.schedule_agenda/)
})

test('moving onto an assigned station parks the displaced team so two teams can swap without stale source data', async () => {
  const a = {key: 'a', ids: [2], day: '2026-10-20', name: '甲组', sourceName: '甲站', cells: [{station_id: 1, column_key: 'a', revision: 1}]}
  const b = {key: 'b', ids: [3], day: '2026-10-20', name: '乙组', sourceName: '乙站', cells: [{station_id: 2, column_key: 'a', revision: 1}]}
  const shelf = {value: [a, b]}, picked = {value: 'a'}, calls = []
  const context = vm.createContext({
    dragged: {value: null}, shelf, pickedShelf: picked, canEdit: {value: true}, loading: {value: false}, shelfSaving: {value: false},
    props: {mode: 'online'}, board: {value: {columns: [{key: 'a'}]}}, draft: {value: {}},
    scheduleCellEditable: () => true, coverageQuery: () => ({mode: 'online'}),
    shelfItem: row => row.station_id === 2 ? b : null,
    sameIds: (a, b) => JSON.stringify(a) === JSON.stringify(b),
    window: {confirm: () => true, dispatchEvent: () => {}}, Event: class {},
    axios: {put: async (_, data) => calls.push(data)},
    removeShelf: key => {shelf.value = shelf.value.filter(s => s.key !== key); if (picked.value === key) picked.value = null},
    shelfOpen: {value: true}, notice: {value: ''}, loadBoard: async () => {}, retryBoard: async () => {},
  })
  const script = source('components/InspectionSchedulePanel.vue')
  vm.runInContext(script.slice(script.indexOf('async function dropOn'),script.indexOf('async function openBulk')), context)
  await context.dropOn({station_id: 2, station_name: '乙站', cells: {a: {status: 'assigned', revision: 1}}}, {key: 'a', label: '安全'})
  assert.equal(calls[0].source.cells[0].station_id, 1)
  assert.equal(shelf.value.length, 1)
  assert.equal(shelf.value[0].name, '乙组')
  assert.equal(shelf.value[0].cells.length, 0, 'displaced plan has no stale source to clear')
  picked.value = shelf.value[0].key
  await context.dropOn({station_id: 1, station_name: '甲站', cells: {a: {status: 'unassigned', revision: 2}}}, {key: 'a', label: '安全'})
  assert.equal(calls[1].source, undefined)
  assert.equal(calls[1].inspector_ids[0], 3)
  assert.equal(shelf.value.length, 0)
})
