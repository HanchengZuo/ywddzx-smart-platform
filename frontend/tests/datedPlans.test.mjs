import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { dateSelection, datePeriod, planningDateLabel, planSession, personnelApplyPlan } from '../src/utils/datedPlans.js'

test('date choice is sorted, deduplicated and restricted to server eligible days',()=>{
  const options=[{day:'2026-10-20'},{day:'2026-11-02'}]
  assert.deepEqual(dateSelection(['2026-11-02','2026-10-20','2026-10-20','2026-10-19'],options),['2026-10-20','2026-11-02'])
  assert.deepEqual(dateSelection([],options),[])
})

test('future adoption focuses the correct year quarter and month',()=>{
  assert.deepEqual(datePeriod('2027-01-04'),{year:2027,month:1,quarter:1})
  assert.deepEqual(datePeriod('2026-12-31'),{year:2026,month:12,quarter:4})
  assert.deepEqual(datePeriod(''),{})
  assert.throws(()=>datePeriod('2027/01/04'))
  assert.equal(planningDateLabel('2027-01-04'),'2027-01-04 · 星期一')
})

test('per-day drafts keep unsaved moves independent and send only dated choices',()=>{
  const first={context:{day:'2026-10-20',revision:2},managerModes:{1:'offline'},preview:{source:'generated',seed:'seed20',token:'token20',moves:[{person_id:4,leader_id:1}],groups:[{name:'untrusted'}]}}
  const second={context:{day:'2026-10-21',revision:7},managerModes:{1:'online'},preview:{source:'current',token:'token21',moves:[]}}
  const sessions={'2026-10-21':second}
  assert.equal(planSession('2026-10-20','2026-10-20',first,sessions),first)
  assert.equal(planSession('2026-10-21','2026-10-20',first,sessions),second)
  assert.equal(personnelApplyPlan(first).groups,undefined)
  assert.deepEqual(personnelApplyPlan(first).moves,[{person_id:4,leader_id:1}])
  assert.equal(personnelApplyPlan(second).token,'token21')
  assert.equal(personnelApplyPlan(second).revision,7)
  assert.equal(personnelApplyPlan({preview:null}),null)
  assert.deepEqual(second.preview.moves,[])
})

test('adopting future personnel does not destroy the open dialog by switching its parent week',async()=>{
  const source=readFileSync(new URL('../src/views/inspection/StaffAvailabilityView.vue',import.meta.url),'utf8')
  const context=vm.createContext({week:{value:'2026-10-26'},teamsOpen:{value:true},notice:{value:''},
    timer:null,clearTimeout(){},nextTick:async()=>{},load:async()=>{},polling:{pause(){},start(){}}})
  vm.runInContext(source.slice(source.indexOf('async function onTeamsSaved'),source.indexOf('const polling =')),context)
  await context.onTeamsSaved({day:'2026-11-02',results:[{},{}]})
  assert.equal(context.week.value,'2026-10-26','keep modal mounted until the user closes it')
  assert.match(context.notice.value,/2 天巡检分组/)
  context.teamsClosed()
  assert.equal(context.week.value,'2026-11-02')
})
