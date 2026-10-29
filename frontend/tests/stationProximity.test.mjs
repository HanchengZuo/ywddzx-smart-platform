import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import { checkStationProximity, proximityResult, distanceMeters, locationErrorMessage } from '../src/utils/stationProximity.js'

const station = { longitude: 121.5, latitude: 31.2 }
const position = { coords: { longitude: 121.4955, latitude: 31.202, accuracy: 15 } }
const dependencies = (extra = {}) => ({ secure: true,
  geolocation: { getCurrentPosition: resolve => resolve(position) },
  loadMap: async () => ({ convertFrom(points, type, callback) {
    assert.deepEqual(points, [121.4955, 31.202]); assert.equal(type, 'gps')
    callback('complete', { locations: [{ getLng: () => 121.5, getLat: () => 31.2 }] })
  } }), ...extra })

test('distance handles same location and known latitude offset with a one-kilometre boundary', () => {
  assert.equal(distanceMeters([121.5, 31.2], [121.5, 31.2]), 0)
  assert.ok(Math.abs(distanceMeters([121.5, 31.2], [121.5, 31.21]) - 1111.95) < 1)
  assert.equal(proximityResult(station, position, [121.5, 31.2]).kind, 'near')
  assert.equal(proximityResult(station, position, [121.5, 31.21]).kind, 'outside')
  assert.equal(proximityResult(station, position, [121.5, 31.20899]).kind, 'uncertain', 'accuracy overlaps boundary')
})

test('poor or invalid accuracy cannot automatically pass even near the station', () => {
  for (const accuracy of [301, null, undefined, NaN, -1, 0]) {
    assert.equal(proximityResult(station, { coords: { accuracy } }, [121.5, 31.2]).kind, 'uncertain')
  }
  assert.equal(proximityResult(station, { coords: { accuracy: 4000 } }, [121.5, 31.4]).kind, 'outside')
})

test('actual check uses official converted coordinates rather than comparing raw WGS84 GPS', async () => {
  let requested = 0
  const value = await checkStationProximity(station, dependencies({ geolocation: {
    getCurrentPosition(resolve, reject, options) {
      requested++
      assert.deepEqual(options, { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 })
      resolve(position)
    },
  } }))
  assert.equal(value.kind, 'near'); assert.equal(value.distance, 0); assert.equal(requested, 1)
})

test('missing station coordinate avoids any permission/map request; invalid locations never fabricate distance', async () => {
  for (const target of [null, {}, { longitude: '', latitude: 31 }, { longitude: 0, latitude: 0 }]) {
    const result = await checkStationProximity(target, { loadMap: () => assert.fail('no map') })
    assert.equal(result.kind, 'unavailable')
  }
  await assert.rejects(checkStationProximity(station, dependencies({ geolocation: {
    getCurrentPosition: resolve => resolve({ coords: { longitude: NaN, latitude: 0 } }),
  } })), /设备返回的位置无效/)
  assert.throws(() => proximityResult(station, position, []), /坐标转换失败/)
})

test('denial, unsupported/insecure browsers and conversion failures have non-blocking explanatory messages', async () => {
  await assert.rejects(checkStationProximity(station, dependencies({ secure: false })), /HTTPS/)
  await assert.rejects(checkStationProximity(station, dependencies({ geolocation: null })), /不支持定位/)
  for (const code of [1, 2, 3]) {
    await assert.rejects(checkStationProximity(station, dependencies({ geolocation: { getCurrentPosition: (yes, no) => no({ code }) } })), error => error.code === code)
    assert.ok(locationErrorMessage({ code }).length > 10)
  }
  await assert.rejects(checkStationProximity(station, dependencies({ loadMap: async () => ({ convertFrom: (_p, _t, cb) => cb('error', {}) }) })), /转换暂不可用/)
  await assert.rejects(checkStationProximity(station, dependencies({ loadMap: async () => { throw new Error('SDK网络失败') } })), /SDK网络失败/)
})

test('cancelled requests and late GPS callbacks cannot load a map or continue checks', async () => {
  const controller = new AbortController()
  let gps
  const request = checkStationProximity(station, dependencies({ signal: controller.signal,
    geolocation: { getCurrentPosition: resolve => { gps = resolve } }, loadMap: () => assert.fail('late map load'),
  }))
  controller.abort()
  await assert.rejects(request, /取消/)
  gps(position)
  await new Promise(resolve => setImmediate(resolve))
})

test('a stalled SDK or GPS does not leave the workflow waiting beyond ten seconds', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const request = checkStationProximity(station, dependencies({ geolocation: { getCurrentPosition() {} } }))
  t.mock.timers.tick(10000)
  await assert.rejects(request, error => error.code === 3)
})

test('shared modal and both submit pages compile; desktop bypass, opt-out and unmount cancellation stay available', () => {
  for (const file of ['components/StationLocationReminder.vue', 'views/inspection/RegisterView.vue', 'views/inspection/MyIssuesView.vue']) {
    const source = readFileSync(new URL('../src/' + file, import.meta.url), 'utf8')
    const { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: 'location-test' })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: 'location-test', compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    for (const style of descriptor.styles) assert.deepEqual(compileStyle({ source: style.content, id: 'location-test', scoped: style.scoped }).errors, [])
    if (file.startsWith('views')) {
      assert.equal((source.match(/<StationLocationReminder /g) || []).length, 1)
      assert.match(source, /if \(!await stationLocationRef.value.confirm\(/)
      assert.doesNotMatch(source, /formData.append\(['"](?:latitude|longitude|location|accuracy)/)
    } else {
      assert.match(source, /if \(!window.matchMedia\('\(max-width: 768px\)'\).matches\) return true/)
      assert.match(source, /返回核对/); assert.match(source, /仍然提交/); assert.match(source, /跳过核对并提交/)
      assert.match(source, /@cancel.prevent="finish\(false\)"/)
      assert.match(source, /onBeforeUnmount\(\(\) => \{ disposed = true; finish\(false\) \}\)/)
      assert.match(source, /request !== sequence/)
    }
  }
})
