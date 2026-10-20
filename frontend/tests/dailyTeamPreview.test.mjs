import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
import {movePreviewStudent} from '../src/utils/dailyTeamPreview.js'

function fixture() {
  const leader = id => ({id,display_name:'管理'+id,position:'管理人员',mode:'offline',leader_id:id,group_name:'外勤管理'+id+'组'})
  const student = {id:10,display_name:'学生甲',position:'大学生',mode:'offline',leader_id:1,group_name:'外勤管理1组'}
  const preview = {seed:'seed',token:'token',groups:[
    {name:'外勤管理1组',mode:'offline',leader_id:1,members:[leader(1),student]},
    {name:'外勤管理2组',mode:'offline',leader_id:2,members:[leader(2)]},
  ]}
  return {preview,people:[leader(1),leader(2),student].map(p=>({...p,available:true,station_modes:[],actual_modes:[]}))}
}

test('preview moves preserve evidence and participants without mutating the original; video can be empty initially', () => {
  const {preview,people} = fixture()
  const original = structuredClone(preview)
  const moved = movePreviewStudent(preview,people,10,2)
  assert.deepEqual(preview,original)
  assert.equal(moved.token,'token')
  assert.equal(moved.seed,'seed')
  assert.equal(moved.student_leaders['10'],2)
  assert.equal(moved.groups.find(g=>g.leader_id===2).members.length,2)
  assert.deepEqual(moved.groups.map(g=>g.name), preview.groups.map(g=>g.name), 'drop targets must not jump to new positions after a move')
  assert.equal(moved.groups.find(g=>g.leader_id===2).members[0].id,2,'leader remains first')
  const video = movePreviewStudent(moved,people,10,null)
  assert.equal(video.groups.find(g=>g.mode==='online').members[0].id,10)
  assert.deepEqual(video.student_leaders,{'10':null})
  const back = movePreviewStudent(video,people,10,1)
  assert.deepEqual(back.groups.flatMap(g=>g.members.map(p=>p.id)).sort((a,b)=>a-b),[1,2,10])
  assert.equal(back.groups.find(g=>g.leader_id===1).members.length,2)
})

test('preview refuses managers, busy/missing students, invalid leaders and cross-mode actual/plan conflicts', () => {
  const {preview,people} = fixture()
  assert.throws(()=>movePreviewStudent(preview,people,1,2),/大学生/)
  assert.throws(()=>movePreviewStudent(preview,people,999,2),/大学生/)
  assert.throws(()=>movePreviewStudent(preview,people,10,999),/带队/)
  assert.throws(()=>movePreviewStudent(preview,people.map(p=>({...p,available:false})),10,2),/有空/)
  for (const property of ['station_modes','actual_modes']) {
    const locked = people.map(p=>p.id!==10?p:{...p,[property]:property==='station_modes'?['offline']:[{mode:'offline',count:1}]})
    assert.throws(()=>movePreviewStudent(preview,locked,10,null),/派工或巡检实绩/)
    assert.equal(movePreviewStudent(preview,locked,10,2).student_leaders['10'],2)
  }
})

test('the preview drop handler makes no request or successful-save event until confirm, with drag data fallback', async () => {
  const {preview,people} = fixture()
  const context = vm.createContext({
    draggingStudent:{value:null},selectedStudent:{value:null},editable:{value:true},loading:{value:false},saving:{value:false},
    preview:{value:preview},error:{value:''},context:{value:{people}},displayGroups:{value:preview.groups},movePreviewStudent,
    axios:{post:()=>{throw new Error('must not save a preview')}},emit:()=>{throw new Error('must not emit saved')},
  })
  const source = readFileSync(new URL('../src/components/DailyInspectionTeams.vue',import.meta.url),'utf8')
  vm.runInContext(source.slice(source.indexOf('async function dropStudent'),source.indexOf('let controller,')),context)
  await context.dropStudent(preview.groups[1],{dataTransfer:{getData:()=> '10'}})
  assert.equal(context.preview.value.student_leaders['10'],2)
  assert.equal(context.preview.value.token,'token')
  assert.equal(context.selectedStudent.value,null)
  assert.equal(context.saving.value,false)
})

test('confirmation sends only preview student choices alongside the original seed and evidence token', async () => {
  const {preview,people} = fixture()
  const moved = movePreviewStudent(preview,people,10,null),calls=[]
  const context = vm.createContext({editable:{value:true},saving:{value:false},loading:{value:false},preview:{value:moved},
    error:{value:''},context:{value:{day:'2026-10-20',revision:4}},managerModes:{value:{1:'offline',2:'offline'}},disposed:false,
    dialog:{value:{close(){}}},emit:(...args)=>calls.push(args),
    axios:{post:async(url,body)=>{calls.push({url,body});return {data:{groups:moved.groups}}}},
  })
  const source = readFileSync(new URL('../src/components/DailyInspectionTeams.vue',import.meta.url),'utf8')
  vm.runInContext(source.slice(source.indexOf('async function submit'),source.indexOf('function confirm()')),context)
  await context.submit('confirm')
  const body=JSON.parse(JSON.stringify(calls[0].body))
  assert.deepEqual(body.student_leaders,{'10':null})
  assert.equal(body.seed,'seed')
  assert.equal(body.token,'token')
  assert.equal(body.groups,undefined)
  assert.equal(body.revision,4)
  assert.equal(calls[2][0],'saved')
})
