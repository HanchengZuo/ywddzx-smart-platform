import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { reactive } from 'vue'
import {
  movePreviewStudent,
  movePreviewMember,
  currentTeamDraft,
} from '../src/utils/dailyTeamPreview.js'

function fixture() {
  const leader = (id) => ({
    id,
    display_name: '管理' + id,
    position: '管理人员',
    mode: 'offline',
    leader_id: id,
    group_name: '外勤管理' + id + '组',
  })
  const student = {
    id: 10,
    display_name: '学生甲',
    position: '大学生',
    mode: 'offline',
    leader_id: 1,
    group_name: '外勤管理1组',
  }
  const preview = {
    seed: 'seed',
    token: 'token',
    groups: [
      { name: '外勤管理1组', mode: 'offline', leader_id: 1, members: [leader(1), student] },
      { name: '外勤管理2组', mode: 'offline', leader_id: 2, members: [leader(2)] },
    ],
  }
  return {
    preview,
    people: [leader(1), leader(2), student].map((p) => ({
      ...p,
      available: true,
      station_modes: [],
      actual_modes: [],
    })),
  }
}

test('current saved Vue reactive groups can become a draft without cloning proxies or mutating state', () => {
  const { preview, people } = fixture()
  const context = reactive({ ...preview, current_token: 'token-current', revision: 2 })
  const draft = currentTeamDraft(context)
  const changed = movePreviewMember(draft, people, 1, null)
  assert.equal(changed.source, 'current')
  assert.equal(changed.token, 'token-current')
  assert.equal(context.groups[0].members.length, 2)
  assert.equal(changed.groups.some(g => g.leader_id === 1), false)
})

test('manager can dissolve a field team into video and restore only their own team', () => {
  const { preview, people } = fixture()
  const original = structuredClone(preview)
  const moved = movePreviewMember(preview, people, 1, null)
  assert.deepEqual(preview, original)
  assert.equal(
    moved.groups.some((g) => g.leader_id === 1),
    false,
  )
  assert.deepEqual(
    moved.groups.find((g) => g.mode === 'online').members.map((p) => p.id),
    [1, 10],
  )
  assert.deepEqual(moved.moves, [{ person_id: 1, leader_id: null }])
  const restored = movePreviewMember(moved, people, 1, 1)
  assert.deepEqual(
    restored.groups.find((g) => g.leader_id === 1).members.map((p) => p.id),
    [1],
  )
  assert.throws(() => movePreviewMember(preview, people, 1, 2), /一位管理人员/)
})

test('current draft preserves original evidence; dispatched source and target or busy/actual members cannot change', () => {
  const { preview, people } = fixture()
  const context = { ...preview, current_token: 'saved-token', day: '2026-10-22', revision: 4 }
  const draft = currentTeamDraft(context)
  assert.equal(draft.source, 'current')
  assert.equal(draft.token, 'saved-token')
  const moved = movePreviewMember(draft, people, 10, 2)
  assert.deepEqual(context.groups, preview.groups)
  assert.deepEqual(moved.moves, [{ person_id: 10, leader_id: 2 }])
  for (const idx of [0, 1]) {
    const locked = structuredClone(draft)
    locked.groups[idx].dispatch_locked = true
    assert.throws(() => movePreviewMember(locked, people, 10, 2), /派工/)
  }
  assert.throws(
    () =>
      movePreviewMember(
        draft,
        people.map((p) => ({ ...p, available: false })),
        1,
        null,
      ),
    /有空/,
  )
  const actual = people.map((p) =>
    p.id === 10 ? { ...p, actual_modes: [{ mode: 'offline' }] } : p,
  )
  assert.throws(() => movePreviewMember(draft, actual, 1, null), /实绩/)
})

test('preview moves preserve evidence and participants without mutating the original; video can be empty initially', () => {
  const { preview, people } = fixture()
  const original = structuredClone(preview)
  const moved = movePreviewStudent(preview, people, 10, 2)
  assert.deepEqual(preview, original)
  assert.equal(moved.token, 'token')
  assert.equal(moved.seed, 'seed')
  assert.equal(moved.student_leaders['10'], 2)
  assert.equal(moved.groups.find((g) => g.leader_id === 2).members.length, 2)
  assert.deepEqual(
    moved.groups.map((g) => g.name),
    preview.groups.map((g) => g.name),
    'drop targets must not jump to new positions after a move',
  )
  assert.equal(moved.groups.find((g) => g.leader_id === 2).members[0].id, 2, 'leader remains first')
  const video = movePreviewStudent(moved, people, 10, null)
  assert.equal(video.groups.find((g) => g.mode === 'online').members[0].id, 10)
  assert.deepEqual(video.student_leaders, { 10: null })
  const back = movePreviewStudent(video, people, 10, 1)
  assert.deepEqual(
    back.groups.flatMap((g) => g.members.map((p) => p.id)).sort((a, b) => a - b),
    [1, 2, 10],
  )
  assert.equal(back.groups.find((g) => g.leader_id === 1).members.length, 2)
})

test('preview refuses managers, busy/missing students, invalid leaders and cross-mode actual/plan conflicts', () => {
  const { preview, people } = fixture()
  assert.throws(() => movePreviewStudent(preview, people, 1, 2), /大学生/)
  assert.throws(() => movePreviewStudent(preview, people, 999, 2), /大学生/)
  assert.throws(() => movePreviewStudent(preview, people, 10, 999), /带队/)
  assert.throws(
    () =>
      movePreviewStudent(
        preview,
        people.map((p) => ({ ...p, available: false })),
        10,
        2,
      ),
    /有空/,
  )
  for (const property of ['station_modes', 'actual_modes']) {
    const locked = people.map((p) =>
      p.id !== 10
        ? p
        : {
            ...p,
            [property]:
              property === 'station_modes' ? ['offline'] : [{ mode: 'offline', count: 1 }],
          },
    )
    if(property === 'actual_modes') assert.throws(() => movePreviewStudent(preview, locked, 10, null), /派工或巡检实绩/)
    else assert.equal(movePreviewStudent(preview, locked, 10, null).student_leaders['10'], null)
    assert.equal(movePreviewStudent(preview, locked, 10, 2).student_leaders['10'], 2)
  }
})

test('unstarted field groups receive returned-free members without mutating saved groups', () => {
  const { preview, people } = fixture()
  const free={id:20,display_name:'重新有空',position:'大学生',available:true,station_modes:[],actual_modes:[]}
  const context=reactive({...preview,current_token:'current',unassigned_people:[free]})
  context.groups[0].has_dispatch=true
  context.groups[0].dispatch_locked=false
  const draft=currentTeamDraft(context)
  const joined=movePreviewMember(draft,[...people,free],20,1)
  assert.equal(joined.groups[0].members.length,3)
  assert.equal(joined.unassigned_people.length,0)
  assert.equal(context.unassigned_people.length,1)
  assert.equal(context.groups[0].members.length,2)
  assert.deepEqual(joined.moves,[{person_id:20,leader_id:1}])
  const video=movePreviewMember(currentTeamDraft(context),[...people,free],20,null)
  assert.equal(video.groups.find(g=>g.mode==='online').members[0].id,20)
  const locked=currentTeamDraft(context)
  locked.groups[0].dispatch_locked=true
  assert.throws(()=>movePreviewMember(locked,[...people,free],20,1),/派工/)
  assert.throws(()=>movePreviewMember(draft,people,20,1),/有空/)
})

test('pending field plans allow transfers; video plans and actual mode conflicts remain protected', () => {
  const {preview,people}=fixture()
  const field=people.map(p=>p.id===10?{...p,station_modes:['offline']}:p)
  assert.equal(movePreviewMember(preview,field,10,2).moves[0].leader_id,2)
  assert.equal(movePreviewMember(preview,field,10,null).moves[0].leader_id,null)
  const video=people.map(p=>p.id===10?{...p,station_modes:['online']}:p)
  assert.throws(()=>movePreviewMember(preview,video,10,2),/派工/)
})

test('the preview drop handler makes no request or successful-save event until confirm, with drag data fallback', async () => {
  const { preview, people } = fixture()
  const context = vm.createContext({
    draggingStudent: { value: null },
    selectedStudent: { value: null },
    editable: { value: true },
    loading: { value: false },
    saving: { value: false },
    preview: { value: preview },
    error: { value: '' },
    success: { value: '' },
    context: { value: { people } },
    displayGroups: { value: preview.groups },
    movePreviewMember,
    currentTeamDraft,
    axios: {
      post: () => {
        throw new Error('must not save a preview')
      },
    },
    emit: () => {
      throw new Error('must not emit saved')
    },
    personLocked: () => false,
    groupLocked: () => false,
  })
  const source = readFileSync(
    new URL('../src/components/DailyInspectionTeams.vue', import.meta.url),
    'utf8',
  )
  vm.runInContext(
    source.slice(source.indexOf('async function dropStudent'), source.indexOf('let controller,')),
    context,
  )
  await context.dropStudent(preview.groups[1], { dataTransfer: { getData: () => '10' } })
  assert.deepEqual(JSON.parse(JSON.stringify(context.preview.value.moves)), [
    { person_id: 10, leader_id: 2 },
  ])
  assert.equal(context.preview.value.token, 'token')
  assert.equal(context.selectedStudent.value, null)
  assert.equal(context.saving.value, false)
})

test('adoption sends only member move choices and original evidence then reloads without closing the dialog', async () => {
  const { preview, people } = fixture()
  const moved = { ...movePreviewMember(preview, people, 10, null), source: 'generated' },
    calls = []
  const context = vm.createContext({
    editable: { value: true },
    saving: { value: false },
    loading: { value: false },
    preview: { value: moved },
    error: { value: '' },
    success: { value: '' },
    context: { value: { day: '2026-10-20', revision: 4 } },
    managerModes: { value: { 1: 'offline', 2: 'offline' } },
    disposed: false,
    load: async () => calls.push('reload'),
    window: { dispatchEvent() {} },
    Event: class {},
    emit: (...args) => calls.push(args),
    axios: {
      post: async (url, body) => {
        calls.push({ url, body })
        return { data: { groups: moved.groups } }
      },
    },
  })
  const source = readFileSync(
    new URL('../src/components/DailyInspectionTeams.vue', import.meta.url),
    'utf8',
  )
  vm.runInContext(
    source.slice(source.indexOf('async function submit'), source.indexOf('function confirm()')),
    context,
  )
  await context.submit()
  const body = JSON.parse(JSON.stringify(calls[0].body))
  assert.equal(body.action, 'apply')
  assert.equal(body.source, 'generated')
  assert.deepEqual(body.moves, [{ person_id: 10, leader_id: null }])
  assert.equal(body.seed, 'seed')
  assert.equal(body.token, 'token')
  assert.equal(body.groups, undefined)
  assert.equal(body.revision, 4)
  assert.equal(calls[1], 'reload')
  assert.equal(calls[2][0], 'saved')
  assert.equal(context.preview.value, null)
})
