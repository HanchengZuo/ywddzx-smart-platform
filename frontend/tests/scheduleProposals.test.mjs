import test from 'node:test'
import assert from 'node:assert/strict'
import {groupScheduleProposals} from '../src/utils/scheduleProposals.js'

const assignment = (uid,sid,mode='online',n=0) => ({mode,station_id:sid,station_name:'站'+sid,
  person:{id:uid,display_name:'检查人'+uid},group_name:'检查人'+uid,cells:[{label:'安全'},{label:'计量'},{label:'现场'}],
  before:{offline:0,online:n},after:{offline:0,online:n+1},route_order:n+1,route_km:10})

test('interleaved video station assignments are grouped by person without changing the server proposal',()=>{
  const source=[assignment(1,10,'online',0),assignment(2,20,'online',5),assignment(1,11,'online',1),assignment(2,21,'online',6),assignment(1,12,'online',2)]
  const original=structuredClone(source),groups=groupScheduleProposals(source)
  assert.equal(groups.length,2)
  assert.deepEqual(groups[0].stations.map(s=>s.station_id),[10,11,12])
  assert.deepEqual(groups[1].stations.map(s=>s.station_id),[20,21])
  assert.equal(groups[0].before.online,0)
  assert.equal(groups[0].after.online,3)
  assert.equal(groups[1].before.online,5)
  assert.equal(groups[1].after.online,7)
  assert.deepEqual(source,original)
})

test('identical names and different modes remain separate; field route order and members remain intact',()=>{
  const field={...assignment(1,30,'offline'),team_members:[{id:1},{id:3}]}
  const source=[field,{...field,station_id:31,route_order:2},assignment(1,40),{...assignment(2,41),person:{id:2,display_name:'检查人1'}}]
  const groups=groupScheduleProposals(source)
  assert.equal(groups.length,3)
  assert.deepEqual(groups[0].stations.map(s=>s.route_order),[1,2])
  assert.deepEqual(groups[0].team_members,field.team_members)
  assert.deepEqual(groupScheduleProposals(),[])
})
