import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
import {staffCellPresentation} from '../src/utils/staffScheduling.js'
const source=readFileSync(new URL('../src/views/inspection/StaffAvailabilityView.vue',import.meta.url),'utf8')

test('past delegated work retains its mode, progress and group instead of becoming no records',()=>{
  const dispatch={total:12,completed:3,station_total:2,station_completed:0,percent:25,modes:['offline']}
  const cell={available:true,actual_modes:[],dispatch,planned_modes:['offline'],daily_assignment:{group_name:'外勤测试组'}}
  const state=staffCellPresentation(cell,'2026-10-20','2026-10-21')
  assert.equal(state.label,'现场巡检');assert.equal(state.stage,'实绩');assert.match(state.detail,/3\/12 项.*0\/2 站/)
  assert.equal(staffCellPresentation({...cell,dispatch:{...dispatch,completed:0}},'2026-10-20','2026-10-21').stage,'已派工')
  const busy=staffCellPresentation({...cell,available:false,reason:'休假'},'2026-10-20','2026-10-21')
  assert.equal(busy.label,'没空');assert.equal(busy.detail,'休假')
  assert.equal(staffCellPresentation({available:true,actual_modes:[],planned_modes:[]},'2026-10-20','2026-10-21').label,'有空')
})

function detailHarness(get){
  const context=vm.createContext({
    selection:{value:{person_name:'测试',day:'2026-10-20',revision:1}},editable:{value:true},detailSerial:0,detailController:undefined,
    detailLoading:{value:false},detailError:{value:''},detail:{value:null},disposed:false,AbortController,
    axios:{get},staffCellPresentation,selectionState:{value:null},available:{value:false},reason:{value:'旧说明'},
    historyStatus:{value:'busy'},savedMeta:{value:''},originalRecords:{value:''},armActualsRefresh:()=>{},
  })
  vm.runInContext(source.slice(source.indexOf('async function loadDetail()'),source.indexOf('function close()')),context)
  return context
}
test('fresh server proof removes edit controls even if the board was editable; closing ignores late responses',async()=>{
  let resolve
  const context=detailHarness(()=>new Promise(done=>{resolve=done}))
  const pending=context.loadDetail()
  assert.equal(context.editable.value,false)
  resolve({data:{can_edit:true,day:'2026-10-20',today:'2026-10-21',records:[],cell:{revision:2,reason:'',available:true,read_only:true,has_actual:true,actual_modes:[{mode:'offline',count:1}]}}})
  await pending
  assert.equal(context.selection.value.revision,2);assert.equal(context.editable.value,false)
  assert.equal(context.selectionState.value.stage,'实绩')
  const late=context.loadDetail();context.detailSerial++;context.selection.value=null;context.detail.value=null
  resolve({data:{can_edit:true,cell:{available:true,revision:99}}})
  await late;assert.equal(context.detail.value,null);assert.equal(context.editable.value,false)
})
test('failed or forbidden detail reads never enable editing',async()=>{
  for(const status of [403,500]){
    const context=detailHarness(async()=>{throw {response:{status,data:{error:'无法核对'}}}})
    await context.loadDetail();assert.equal(context.editable.value,false)
    assert.equal(context.detailError.value,'无法核对');assert.equal(context.detailLoading.value,false)
  }
})
