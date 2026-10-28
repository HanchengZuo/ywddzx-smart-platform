import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const source=readFileSync(new URL('../src/components/DailyInspectionTeams.vue',import.meta.url),'utf8')
const body=source.slice(source.indexOf('async function markSelectedBusy()'),source.indexOf('onBeforeUnmount(()'))
function harness({locked=false,fail=false}={}) {
  const calls=[]
  const context=vm.createContext({
    selectedPerson:{value:{id:10,display_name:'甲'}},editable:{value:true},personLocked:()=>locked,
    saving:{value:false},loading:{value:false},context:{value:{day:'2026-11-02',people:[{id:10,display_name:'甲',revision:4}]}},
    busyReason:{value:'培训'},activeDay:{value:'2026-11-02'},disposed:false,success:{value:''},
    axios:{put:async(url,data)=>{calls.push({url,data});if(fail)throw {response:{data:{error:'任务刚刚已有实绩'}}}}},
    load:async()=>calls.push('reload'),emit:(event,data)=>calls.push({event,data}),
    Event:class{constructor(type){this.type=type}},window:{dispatchEvent:event=>calls.push(event.type)},
    warn:message=>calls.push(message),
  })
  vm.runInContext(body,context)
  return {context,calls}
}
test('busy action uses the selected future day and saved availability revision, then reloads live groups and tasks',async()=>{
  const {context,calls}=harness()
  await context.markSelectedBusy()
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])),{url:'/api/staff-availability',data:{available:false,reason:'培训',cells:[{person_name:'甲',day:'2026-11-02',revision:4}]}})
  assert.equal(calls[1],'reload')
  assert.equal(calls[2].event,'saved');assert.equal(calls[2].data.adjusted,true)
  assert.ok(calls.includes('inspection-schedule-changed'))
  assert.ok(calls.includes('inspection-sign-pending-refresh'))
  assert.equal(context.saving.value,false)
})
test('executed, read-only, missing or already-saving selections cannot submit a busy change',async()=>{
  for(const [locked,edit] of [[true,c=>{}],[false,c=>{c.editable.value=false}],[false,c=>{c.selectedPerson.value=null}],[false,c=>{c.saving.value=true}]]){
    const {context,calls}=harness({locked});edit(context)
    await context.markSelectedBusy();assert.deepEqual(calls,[])
  }
})
test('a raced busy change shows the server reason and reloads, without emitting a successful adoption',async()=>{
  const {context,calls}=harness({fail:true})
  await context.markSelectedBusy()
  assert.deepEqual(calls.slice(1),['任务刚刚已有实绩','reload'])
  assert.equal(context.success.value,'');assert.equal(context.saving.value,false)
  assert.match(source,/本次操作将放弃此日期尚未采用的草案/)
})
