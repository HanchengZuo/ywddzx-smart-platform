import test from 'node:test'
import assert from 'node:assert/strict'
import { schedulingBeaconIcon, choosePulseStations, beaconPhase } from '../src/utils/schedulingBeacons.js'

const stations = Array.from({ length: 160 }, (_, index) => ({
  station_id: index + 1, station_name: `站点${index + 1}`, longitude: 121 + index / 1000, latitude: 31 + index / 1000,
}))

test('neon icons are cached, centered SVGs and selected state has a distinct gold palette', () => {
  const normal = schedulingBeaconIcon()
  assert.equal(normal, schedulingBeaconIcon(false))
  assert.notEqual(normal, schedulingBeaconIcon(true))
  const svg = decodeURIComponent(normal.split(',')[1])
  assert.match(svg, /width="40" height="40"/)
  assert.match(svg, /#5bfff2/)
  assert.match(decodeURIComponent(schedulingBeaconIcon(true).split(',')[1]), /#ffd76a/)
  assert.doesNotMatch(svg, /<script|<animate|href=|foreignObject/)
})

test('large datasets have a hard animation budget without changing station data', () => {
  const before = structuredClone(stations)
  for (const budget of [6, 12, 14]) {
    const chosen = choosePulseStations(stations, '', null, budget)
    assert.equal(chosen.length, budget)
    assert.equal(new Set(chosen.map(row => row.station_id)).size, budget)
    assert.ok(chosen.every(row => stations.includes(row)))
  }
  assert.equal(choosePulseStations(stations, '', null, 10000).length, 14)
  assert.deepEqual(stations, before)
})

test('effects are restricted to valid on-screen stations and preserve selected station priority', () => {
  const bounds = [[121.02, 31.02], [121.09, 31.09]]
  const chosen = choosePulseStations([...stations, { station_id: 999, longitude: null, latitude: null }], 76, bounds, 6)
  assert.equal(chosen.length, 6)
  assert.equal(chosen[0].station_id, 76)
  assert.ok(chosen.every(row => row.longitude >= bounds[0][0] && row.longitude <= bounds[1][0]))
  assert.equal(choosePulseStations(stations, 160, bounds, 1)[0].station_id, 21)
  assert.deepEqual(choosePulseStations(stations, '', [[100, 20], [101, 21]], 12), [])
})

test('co-located stations do not stack animated effects; selected station wins that location', () => {
  const overlap = { ...stations[0], station_id: 999 }
  const chosen = choosePulseStations([stations[0], overlap, stations[1]], '999', null, 12)
  assert.deepEqual(chosen, [overlap, stations[1]])
  assert.deepEqual(choosePulseStations(stations, 150, null, 1), [stations[149]])
})

test('disabled or invalid budgets produce no animated overlays', () => {
  for (const budget of [0, -1, undefined, NaN, 'invalid']) assert.deepEqual(choosePulseStations(stations, 1, null, budget), [])
  assert.deepEqual(choosePulseStations([], '', null, 12), [])
  assert.equal(choosePulseStations(stations, '', null, 6.8).length, 6)
})

test('animation phases are stable, staggered and cannot inject CSS', () => {
  assert.equal(beaconPhase(1), beaconPhase('1'))
  assert.notEqual(beaconPhase(1), beaconPhase(2))
  for (const id of [1, null, '<style>bad</style>', 'station']) assert.match(beaconPhase(id), /^-\d{1,4}ms$/)
})
