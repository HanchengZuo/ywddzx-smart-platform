import test from 'node:test'
import assert from 'node:assert/strict'
import { setImmediate } from 'node:timers'
import { createCoverageLoader, coverageKey } from '../src/utils/schedulingCoverageLoader.js'

const quarter = number => ({ mode:'offline',year:2026,quarter:number })
const payload = (query, suffix = '') => ({ period:query, stations:[{ station_id:1,station_name:'甲站' }],
  summary:{ total:2,checked:1,remaining:1 }, regions:[],generated_at:'time' + suffix })
const tick = () => new Promise(resolve => setImmediate(resolve))
function fixture(options = {}) {
  let now = 0, identifier = 0, state
  const timers = new Map(), requests = [], states = []
  const loader = createCoverageLoader({ ...options, now:() => now,
    setTimer:callback => { timers.set(++identifier, callback); return identifier },clearTimer:id => timers.delete(id),
    onChange:next => { state = next; states.push(next) },
    fetchCoverage:(query, signal) => new Promise((resolve,reject) => requests.push({ query,signal,resolve,reject })),
  })
  return { loader,requests,states,timers,state:() => state,advance:ms => { now += ms },
    fire() { const entry = timers.entries().next().value; if (entry) { timers.delete(entry[0]); entry[1]() } },
    async finish(index, value = payload(requests[index].query)) { requests[index].resolve(value); await tick() },
  }
}
test('quick period changes debounce to one request; duplicate choices never overlap', async () => {
  const f = fixture()
  f.loader.select(quarter(1));f.loader.select(quarter(2));f.loader.select(quarter(3))
  assert.equal(f.requests.length, 0);assert.equal(f.timers.size, 1)
  f.fire();assert.deepEqual(f.requests[0].query, quarter(3))
  f.loader.select(quarter(3));assert.equal(f.requests.length, 1)
  await f.finish(0);assert.equal(f.state().loading, false)
  f.loader.dispose()
})
test('new selection immediately aborts previous request and late responses cannot overwrite or populate cache', async () => {
  const f = fixture()
  f.loader.select(quarter(1), { immediate:true })
  f.loader.select(quarter(2))
  assert.equal(f.requests[0].signal.aborted, true)
  await f.finish(0)
  assert.equal(f.state().result, null)
  f.fire();await f.finish(1)
  assert.equal(f.state().result.period.quarter, 2)
  f.loader.select(quarter(1));f.fire()
  assert.equal(f.requests.length, 3)
  assert.equal(f.state().result.period.quarter, 2)
  f.loader.dispose()
})
test('fresh cache is instant and cancels pending work; stale cache stays visible while revalidating', async () => {
  const f = fixture()
  f.loader.select(quarter(1), { immediate:true });await f.finish(0)
  const cached = f.state().result
  f.loader.select(quarter(2));f.loader.select(quarter(1))
  assert.equal(f.state().result, cached);assert.equal(f.state().loading, false)
  assert.equal(f.timers.size, 0);assert.equal(f.requests.length, 1)
  f.advance(30001);f.loader.select(quarter(1))
  assert.equal(f.state().result, cached);assert.equal(f.state().loading, true)
  f.fire();await f.finish(1)
  assert.equal(f.requests.length, 2)
  f.loader.dispose()
})
test('background refresh respects freshness and deduplicates; unchanged station rows retain identity', async () => {
  const f = fixture()
  f.loader.select(quarter(1), { immediate:true });await f.finish(0)
  const previous = f.state().result
  await f.loader.refresh();assert.equal(f.requests.length, 1)
  f.advance(30001)
  const refresh = f.loader.refresh()
  await f.loader.refresh();assert.equal(f.requests.length, 2)
  const response = payload(quarter(1), 'new')
  await f.finish(1, response);assert.equal(await refresh, true)
  assert.equal(f.state().result.stations, previous.stations)
  assert.notEqual(response.stations, previous.stations)
  assert.equal(f.state().result.generated_at, 'timenew')
  f.loader.dispose()
})
test('ordinary errors retain the last result for retry; auth denial clears cache and stops requests', async () => {
  const f = fixture()
  f.loader.select(quarter(1), { immediate:true });await f.finish(0)
  f.advance(30001)
  const failed = f.loader.refresh()
  f.requests[1].reject(new Error('network'));await tick()
  assert.equal(await failed, false)
  assert.equal(f.state().result.period.quarter, 1)
  assert.match(f.state().error, /自动重试/)
  const denied = f.loader.refresh()
  f.requests[2].reject({ response:{ status:403,data:{ error:'权限已取消' } } });await tick()
  assert.equal(await denied, false)
  assert.equal(f.state().result, null);assert.equal(f.state().blocked, true)
  f.loader.select(quarter(2), { immediate:true });await f.loader.refresh()
  assert.equal(f.requests.length, 3)
  f.loader.dispose()
})
test('cache is bounded and is never shared with another view', async () => {
  const f = fixture({ maxEntries:2 })
  for (let q = 1; q <= 3; q++) { f.loader.select(quarter(q), { immediate:true });await f.finish(q - 1) }
  f.loader.select(quarter(1), { immediate:true });assert.equal(f.requests.length, 4)
  const other = fixture();other.loader.select(quarter(3), { immediate:true });assert.equal(other.requests.length, 1)
  f.loader.dispose();other.loader.dispose()
})
test('malformed or mismatched-period responses cannot replace the displayed result or enter cache', async () => {
  const f = fixture()
  f.loader.select(quarter(1), { immediate:true });await f.finish(0)
  f.loader.select(quarter(2), { immediate:true });await f.finish(1, payload(quarter(3)))
  assert.equal(f.state().result.period.quarter, 1)
  assert.match(f.state().error, /自动重试/)
  f.loader.select(quarter(2), { immediate:true });await f.finish(2, '<html>Bad gateway</html>')
  assert.equal(f.state().result.period.quarter, 1)
  f.loader.select(quarter(2), { immediate:true });assert.equal(f.requests.length, 4)
  f.loader.dispose()
})
test('invalid years never fetch; inactive period fields do not change cache identity', () => {
  const f = fixture()
  f.loader.select({ ...quarter(1),year:20 }, { immediate:true })
  assert.equal(f.requests.length, 0);assert.equal(f.state().loading, false)
  assert.equal(coverageKey(quarter(1)), coverageKey({ ...quarter(1),month:10 }))
  f.loader.dispose()
})
test('disposing clears debounce, aborts requests and suppresses all late state updates', async () => {
  const f = fixture()
  f.loader.select(quarter(1));f.loader.dispose();f.fire()
  assert.equal(f.requests.length, 0)
  const g = fixture()
  g.loader.select(quarter(1), { immediate:true });g.loader.dispose()
  const count = g.states.length
  assert.equal(g.requests[0].signal.aborted, true)
  await g.finish(0)
  assert.equal(g.states.length, count)
  g.loader.select(quarter(2));await g.loader.refresh()
  assert.equal(g.requests.length, 1)
})
