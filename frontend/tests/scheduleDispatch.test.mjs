import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { parse, compileScript } from '@vue/compiler-sfc'
import { parse as parseJavascript } from '@babel/parser'

const source = file => readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
for (const file of ['App.vue', 'components/InspectionSchedulePanel.vue', 'components/MeteringAnnualPlan.vue', 'components/DailyInspectionTeams.vue', 'components/AutomaticSchedule.vue', 'components/ScheduleTaskInbox.vue']) {
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
    preview: { value: null }, saving: { value: false }, loading: {value:false}, error: { value: '' },
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
    preview: {value: null}, saving: {value: false}, loading: {value:false}, error: {value: ''},
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

test('automatic dispatch explains coverage balance and interstation distance without online routing or paid AI', () => {
  const script = source('components/AutomaticSchedule.vue')
  assert.match(script,/先补足当月计量年度计划/)
  assert.match(script,/再均衡季度片区覆盖/)
  assert.match(script,/regional_coverage/)
  assert.match(script,/cluster_max_km/)
  assert.doesNotMatch(script,/route_km|SCHEDULE_ORIGIN|2-opt|建议路线排序/)
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

function dispatchHarness(mode = 'offline', fail = false) {
  const item = {id: 17, revision: 2, key: 'shelf:17', name: '外勤甲组'}
  const calls = []
  const keys = mode === 'offline' ? ['a','b','c','d','e','f'] : ['a','b','c']
  const context = vm.createContext({
    dragged: {value: null}, shelf: {value: [item]}, pickedShelf: {value: item.key},
    canEdit: {value: true}, loading: {value: false}, shelfSaving: {value: false}, saving: {value: false},
    props: {mode}, board: {value: {columns: keys.map(key => ({key})), board_token: 'server-token',today:'2026-10-20'}},
    draft: {value: {}}, scheduleCellEditable: c => c.status !== 'completed', coverageQuery: () => ({mode}),
    serial: 0, controller: undefined, polling: {pause() {}, start() {}}, disposed: false,
    selectedCells: {value: ['old']}, error: {value: ''}, updatedTime: {value: ''}, lastSyncedAt: 0,
    shelfOpen: {value: false}, notice: {value: ''},
    window: {confirm() { throw Error('drop must not confirm') }, dispatchEvent: () => calls.push('notify')}, Event: class {},
    axios: {post: async (url, body) => {
      calls.push({url,body})
      if (fail) throw {response: {status: 409, data: {error: '计划已变化'}}}
      return {data: {message: '保存成功',board: {rows: ['server-owned'],shelf: [{id: 18, key: 'shelf:18',name:'被替换组'}]}}}
    }},
    retryBoard: async () => calls.push('reconcile'),
  })
  const script = source('components/InspectionSchedulePanel.vue')
  vm.runInContext(script.slice(script.indexOf('function targetCells'), script.indexOf('async function openBulk')), context)
  const row = {station_id: 2, station_name: '乙站', cells: Object.fromEntries(keys.map(key => [key,{status: 'assigned',revision:3,scheduled_date:'2026-10-20',assignees:[{id:2,display_name:'甲'}],plan_team:{name:'甲组'}}]))}
  return {context, calls, row, item}
}

test('field drop fills whole unfinished row without confirmation and renders authoritative board/shelf immediately', async () => {
  const {context,calls,row} = dispatchHarness()
  row.cells.a.status = 'completed'
  await context.dropOn(row, {key: 'c'})
  assert.equal(calls[0].url, '/api/inspection-schedule/dispatch')
  assert.equal(calls[0].body.action, 'place')
  assert.equal(calls[0].body.shelf_id, 17)
  assert.equal(calls[0].body.cells.length, 5)
  assert.ok(calls[0].body.cells.every(c => c.station_id === 2 && c.column_key !== 'a'))
  assert.equal(context.board.value.rows[0], 'server-owned')
  assert.equal(context.shelf.value[0].name, '被替换组')
  assert.equal(context.pickedShelf.value, null)
  assert.equal(context.shelfSaving.value, false)
})

test('dragging any field cell into shelf submits entire row even if first cell has no assignment', async () => {
  const {context,calls,row} = dispatchHarness()
  row.cells.a.status = 'unassigned'; row.cells.a.assignees = []
  const data = new Map()
  const event = {preventDefault() {},dataTransfer:{setData:(k,v) => data.set(k,v),getData:k => data.get(k)}}
  context.startAssignmentDrag(event,row,{key:'d'})
  context.dragged.value = null // Browser dragend/re-render must not lose the payload.
  await context.stageDragged(event)
  assert.equal(calls[0].body.action, 'park')
  assert.equal(calls[0].body.cells.length, 6)
  assert.equal(context.shelfOpen.value, true)
})

test('video drop targets all three columns; clear sends server board token, not filtered rows', async () => {
  const {context,calls,row} = dispatchHarness('online')
  await context.dropOn(row,{key:'c'})
  assert.equal(calls[0].body.cells.length, 3)
  assert.deepEqual(Array.from(calls[0].body.cells,c=>c.column_key),['a','b','c'])
  context.board.value.board_token = 'latest'
  await context.clearToday()
  const clear = calls.find(c => c.body?.action === 'clear_today')
  assert.equal(clear.body.action, 'clear_today')
  assert.equal(clear.body.board_token, 'latest')
  assert.equal(clear.body.cells, undefined)
  assert.equal(context.shelf.value[0].id,18,'clear renders the returned waiting cards')
  assert.equal(context.shelfOpen.value,true,'clear opens the waiting shelf for immediate redispatch')
})

test('clear-today UI preserves waiting cards and requires plans in the table', () => {
  const panel=source('components/InspectionSchedulePanel.vue')
  assert.match(panel,/:disabled="loading \|\| shelfSaving \|\| !hasTodayPlans \|\| !canEdit"/)
  assert.match(panel,/一键清空今日排班会将表内今日未完成计划转入本区，原有待选安排保留/)
  assert.doesNotMatch(panel,/一键清空今日排班也会清空本区/)
})

test('video row drag skips only immutable completed columns', async () => {
  const {context,calls,row} = dispatchHarness('online')
  row.cells.a.status = 'completed'
  const data = new Map()
  const event = {preventDefault(){},dataTransfer:{setData:(k,v)=>data.set(k,v),getData:k=>data.get(k)}}
  context.startAssignmentDrag(event,row)
  await context.stageDragged(event)
  assert.equal(calls[0].body.action,'park')
  assert.deepEqual(Array.from(calls[0].body.cells,c=>c.column_key),['b','c'])
})

test('today shelf refuses to drag a future or mixed-day row, without clearing any cells', () => {
  for (const mode of ['offline','online']) {
    const {context,calls,row} = dispatchHarness(mode)
    row.cells.b.scheduled_date = '2026-10-21'
    let prevented = false
    context.startAssignmentDrag({preventDefault() {prevented=true}},row)
    assert.equal(prevented,true)
    assert.equal(context.dragged.value,null)
    assert.equal(calls.length,0)
    assert.equal(row.cells.a.assignees.length,1)
  }
})

test('failed dispatch reconciles rather than inventing or deleting a shelf card', async () => {
  const {context,calls,row,item} = dispatchHarness('offline',true)
  await context.dropOn(row,{key:'a'})
  assert.equal(context.shelf.value[0], item)
  assert.equal(context.notice.value, '计划已变化')
  assert.equal(calls[1], 'reconcile')
  assert.equal(context.shelfSaving.value, false)
})

test('daily grouping remains disabled while any roster member is unconfirmed', () => {
  const script = source('components/DailyInspectionTeams.vue')
  const context = vm.createContext({computed: fn => ({get value() {return fn()}}),
    context: {value: {working:true,unconfirmed:['甲'],people:[{}]}}, managers:{value:[{id:2}]},managerModes:{value:{2:'offline'}}})
  vm.runInContext(script.slice(script.indexOf('const ready ='),script.indexOf('const displayGroups ='))+';globalThis.result=ready',context)
  assert.equal(context.result.value,false)
  context.context.value.unconfirmed=[]
  assert.equal(context.result.value,true)
})
