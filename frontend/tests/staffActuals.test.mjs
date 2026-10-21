import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { actualsRefreshDelay } from '../src/utils/staffActuals.js'
import { staffCellPresentation } from '../src/utils/staffScheduling.js'

const source = readFileSync(new URL('../src/views/inspection/StaffAvailabilityView.vue',import.meta.url),'utf8')

test('cutover uses server Shanghai timestamps, exactly 17:00 and no client clock or rapid polling', () => {
  const metadata={actuals_pending:true,actuals_release_at:'2026-10-21T17:00:00+08:00',server_now:'2026-10-21T16:59:59+08:00'}
  assert.equal(actualsRefreshDelay(metadata),1100)
  assert.equal(actualsRefreshDelay({...metadata,server_now:'2026-10-21T09:00:00Z'}),100)
  assert.equal(actualsRefreshDelay({...metadata,actuals_pending:false}),null)
  assert.equal(actualsRefreshDelay({...metadata,server_now:'invalid'}),null)
  assert.equal(actualsRefreshDelay({}),null)
  assert.match(source,/clearTimeout\(actualsTimer\)/)
  assert.doesNotMatch(source,/setInterval/)
})

test('released mixed actuals override a single planned mode without dropping either count or progress', () => {
  const cell={available:true,planned_modes:['offline'],actual_modes:[{mode:'offline',count:3},{mode:'online',count:2}],
    dispatch:{modes:['offline'],total:12,completed:3,station_completed:0,station_total:2}}
  const state=staffCellPresentation(cell,'2026-10-21','2026-10-21')
  assert.equal(state.tone,'mixed');assert.equal(state.label,'现场 / 视频');assert.equal(state.stage,'实绩')
  assert.match(state.detail,/现场 3 张检查表.*视频 2 张检查表.*3\/12 项/)
  const video=staffCellPresentation({...cell,actual_modes:[{mode:'online',count:1}],dispatch:{...cell.dispatch,completed:0}},'2026-10-21','2026-10-21')
  assert.equal(video.tone,'online');assert.equal(video.stage,'实绩')
  const planned=staffCellPresentation({...cell,actuals_pending:true,actual_modes:[],dispatch:{...cell.dispatch,completed:0}},'2026-10-21','2026-10-21')
  assert.equal(planned.tone,'offline');assert.equal(planned.stage,'已派工')
  assert.equal(staffCellPresentation({...cell,available:false,reason:'培训'},'2026-10-21','2026-10-21').label,'没空')
})

function refreshHarness(update) {
  const calls=[]
  const context=vm.createContext({
    actualsTimer:undefined,actualsRefreshDelay,setTimeout:(fn,delay)=>{calls.push({fn,delay});return calls.length},clearTimeout:()=>{},
    disposed:false,blocked:{value:false},document:{hidden:false},navigator:{onLine:true},saving:{value:false},
    dialog:{value:{open:true}},selection:{value:{person_name:'甲',day:'2026-10-21',revision:1}},
    editable:{value:true},available:{value:false},reason:{value:'出差'},historyStatus:{value:'auto'},
    load:async()=>calls.push('board'),loadDetail:async()=>{calls.push('detail');context.available.value=true;context.reason.value='';update(context)},
  })
  vm.runInContext(source.slice(source.indexOf('function armActualsRefresh('),source.indexOf('async function openCell(')),context)
  return {context,calls}
}

test('cutover reloads the open detail and board, and cannot retain editable controls after actuals release', async () => {
  const {context,calls}=refreshHarness(ctx=>{ctx.editable.value=false})
  await context.refreshActuals()
  assert.deepEqual(calls,['detail','board']);assert.equal(context.editable.value,false)
  assert.equal(context.reason.value,'')
})

test('cutover retains unsaved draft only for the same still-editable cell and saved revision', async () => {
  const {context}=refreshHarness(()=>{})
  await context.refreshActuals();assert.equal(context.available.value,false);assert.equal(context.reason.value,'出差')
  const changed=refreshHarness(ctx=>{ctx.selection.value.revision=2})
  await changed.context.refreshActuals();assert.equal(changed.context.reason.value,'')
  const reopened=refreshHarness(ctx=>{ctx.selection.value={...ctx.selection.value}})
  await reopened.context.refreshActuals();assert.equal(reopened.context.reason.value,'')
})

test('cutover never competes with a save or hidden/offline view, and cancels stale timers', async () => {
  const {context,calls}=refreshHarness(()=>{})
  context.saving.value=true;await context.refreshActuals()
  assert.equal(calls.length,1);assert.equal(calls[0].delay,1000)
  context.saving.value=false;context.document.hidden=true;await context.refreshActuals();assert.equal(calls.length,1)
  context.document.hidden=false;context.navigator.onLine=false;await context.refreshActuals();assert.equal(calls.length,1)
  context.armActualsRefresh({actuals_pending:false});assert.equal(calls.length,1)
})

for(const file of ['views/inspection/StaffAvailabilityView.vue','components/StaffDispatchDetails.vue']){
  test(`${file} compiles with released actuals and preserved plan details`,()=>{
    const {descriptor}=parse(readFileSync(new URL('../src/'+file,import.meta.url),'utf8'))
    const script=compileScript(descriptor,{id:'staff-actuals'})
    const template=compileTemplate({source:descriptor.template.content,filename:file,id:'staff-actuals',compilerOptions:{bindingMetadata:script.bindings}})
    assert.deepEqual(template.errors,[])
    for(const style of descriptor.styles)assert.deepEqual(compileStyle({source:style.content,id:'staff-actuals',scoped:style.scoped}).errors,[])
  })
}
