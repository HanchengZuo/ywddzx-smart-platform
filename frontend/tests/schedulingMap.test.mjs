import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { coverageQuery, currentCoveragePeriod, stationCoordinates, filterUncoveredStations } from '../src/utils/schedulingCoverage.js'
import { operationsMenuPages } from '../src/config/operationsCatalog.js'

test('Beijing date defaults correctly across UTC year and quarter boundaries', () => {
  assert.deepEqual(currentCoveragePeriod(new Date('2026-12-31T16:01:00Z')), { mode:'offline',year:2027,quarter:1,month:1 })
  assert.equal(currentCoveragePeriod(new Date('2026-09-30T16:00:00Z')).quarter, 4)
})
test('query only sends quarter for on-site and month for video; invalid values cannot query', () => {
  const draft = { mode:'offline',year:2026,quarter:4,month:10 }
  assert.deepEqual(coverageQuery(draft), { mode:'offline',year:2026,quarter:4 })
  assert.deepEqual(coverageQuery({ ...draft,mode:'online' }), { mode:'online',year:2026,month:10 })
  for (const value of [{ ...draft,quarter:0 },{ ...draft,quarter:1.1 },{ ...draft,year:1999 },{ ...draft,year:2101 },{ ...draft,mode:'bad' },{ ...draft,mode:'online',month:13 }]) assert.throws(() => coverageQuery(value))
})
test('missing or invalid coordinates stay in the list but cannot make false pins', () => {
  for (const [longitude,latitude] of [[null,null],['',''],[undefined,31],[0,0],[181,31],[121,91],['bad',31]]) assert.equal(stationCoordinates({ longitude,latitude }), null)
  assert.deepEqual(stationCoordinates({ longitude:'121.5',latitude:'31.2' }), [121.5,31.2])
})
test('local region and keyword filters do not mutate the server coverage result', () => {
  const rows = [{ station_id:1,station_name:'甲站',region:'浦东',address:'甲路' },{ station_id:2,station_name:'乙站',region:'嘉青',address:'上海 Road' }]
  assert.deepEqual(filterUncoveredStations(rows, '浦东', '甲路'), [rows[0]])
  assert.deepEqual(filterUncoveredStations(rows, '', 'ROAD'), [rows[1]])
  assert.equal(filterUncoveredStations(rows, '', '').length, 2)
  assert.deepEqual(filterUncoveredStations(rows, '嘉青', '甲站'), [])
  assert.equal(rows.length, 2)
})
test('menu is below station map and has an independent view permission', () => {
  const index = operationsMenuPages.findIndex(page => page.key === 'station-map')
  assert.equal(operationsMenuPages[index + 1].permission, 'view_scheduling_map')
  assert.equal(operationsMenuPages[index + 1].path, '/inspection/scheduling-map')
})
for (const path of ['components/SchedulingMapCanvas.vue','views/inspection/SchedulingMapView.vue','views/inspection/StationMapView.vue']) {
  test(`actual map component compiles: ${path}`, () => {
    const source = readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
    const { descriptor,errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id:'coverage-test' })
    const output = compileTemplate({ source:descriptor.template.content,filename:path,id:'coverage-test',compilerOptions:{ bindingMetadata:script.bindings } })
    assert.deepEqual(output.errors, [])
  })
}
test('SDK loader is shared, deduplicated, and can retry a failed network load', async () => {
  const appended = []
  globalThis.window = { setTimeout, clearTimeout }
  globalThis.document = { createElement:() => ({ remove() { this.removed = true } }),head:{ appendChild:script => appended.push(script) } }
  try {
    const { loadAmapSdk,amapPinIcon } = await import('../src/utils/amapSdk.js?coverage-test')
    const first = loadAmapSdk()
    assert.equal(first, loadAmapSdk())
    assert.equal(appended.length, 1)
    appended[0].onerror()
    await assert.rejects(first, /高德地图/)
    assert.equal(appended[0].removed, true)
    const retry = loadAmapSdk()
    assert.equal(appended.length, 2)
    window.AMap = { Map:class {} }
    appended[1].onload()
    assert.equal(await retry, window.AMap)
    assert.equal(await loadAmapSdk(), window.AMap)
    assert.equal(appended.length, 2)
    assert.equal(amapPinIcon('#abc'), amapPinIcon('#abc'))
    assert.notEqual(amapPinIcon('#abc'), amapPinIcon('#def'))
  } finally { delete globalThis.window; delete globalThis.document }
})
