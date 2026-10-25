import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { groupScheduleProposals } from '../src/utils/scheduleProposals.js'

const source = readFileSync(new URL('../src/components/AutomaticSchedule.vue', import.meta.url), 'utf8')

test('driving minutes/kilometres retain zero and missing values, and legs follow the returned direction', () => {
  const functions = source.slice(source.indexOf('const drivingMinutes'), source.indexOf('const basis'))
  const context = vm.createContext({})
  vm.runInContext(functions, context)
  assert.equal(vm.runInContext('drivingMinutes(0)', context), 0)
  assert.equal(vm.runInContext('drivingMinutes(301)', context), 6)
  assert.equal(vm.runInContext('drivingMinutes(undefined)', context), '—')
  assert.equal(vm.runInContext('drivingKilometers(12500)', context), '12.5')
  assert.equal(vm.runInContext('drivingKilometers(undefined)', context), '—')
  assert.equal(vm.runInContext('drivingLeg({station_id:2},{driving_legs:[{origin_id:1,destination_id:2,seconds:300}]}).seconds', context), 300)
  assert.equal(vm.runInContext('drivingLeg({station_id:1},{driving_legs:[{origin_id:1,destination_id:2,seconds:300}]})', context), undefined)
})

test('grouped cards preserve driving order, complete leg evidence and server token input', () => {
  const common = { mode: 'offline', person: { id: 1 }, driving_seconds: 600, driving_meters: 12500,
    driving_legs: [{ origin_id: 3, destination_id: 1, seconds: 600, meters: 12500 }] }
  const source = [{ ...common, station_id: 3, route_order: 1 }, { ...common, station_id: 1, route_order: 2 }]
  const original = structuredClone(source)
  const groups = groupScheduleProposals(source)
  assert.equal(groups[0].driving_seconds, 600)
  assert.equal(groups[0].driving_meters, 12500)
  assert.deepEqual(groups[0].stations.map(s => s.station_id), [3, 1])
  assert.deepEqual(source, original)
})

test('driving requests remain server-side, failures make an old preview non-applicable, and existing replacement confirmation remains', () => {
  assert.doesNotMatch(source, /restapi\.amap|AMAP_KEY|AMAP_WEB_SERVICE_KEY|cluster_max_km/)
  assert.match(source, /timeout: 90000/)
  assert.match(source, /stale\.value = true/)
  assert.match(source, /!preview\?\.groups\.length \|\| stale \|\| !replaceConfirmed/)
  assert.match(source, /token: preview\.value\.token/)
  assert.match(source, /每周一09:30自动更新/)
  assert.match(source, /站对只采一个方向/)
  assert.match(source, /此处只读数据库/)
})
