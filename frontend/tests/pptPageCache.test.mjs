import test from 'node:test'
import assert from 'node:assert/strict'
import { createPptPageCache } from '../src/utils/pptPageCache.js'

function harness(fetchBlob, limits = {}) {
  let next = 0
  const revoked = []
  const cache = createPptPageCache(fetchBlob, { ...limits, urls: {
    createObjectURL: () => `blob:${++next}`, revokeObjectURL: url => revoked.push(url),
  } })
  return { cache, revoked }
}

test('prefetched and visited pages reuse authenticated results without another request', async () => {
  let calls = 0
  const { cache } = harness(async () => { calls++; return { size: 10 } })
  const first = await cache.get(1)
  await cache.get(2, { prefetch: true })
  const second = cache.peek(2)
  cache.focus(2)
  assert.equal(await cache.get(2), second)
  assert.equal(await cache.get(1), first)
  assert.equal(calls, 2)
  cache.dispose()
})

test('in-flight requests deduplicate and parallelism is bounded', async () => {
  const resolvers = []
  const { cache } = harness(() => new Promise(resolve => resolvers.push(resolve)))
  const first = cache.get(1), same = cache.get(1), second = cache.get(2), third = cache.get(3)
  assert.equal(first, same)
  await Promise.resolve()
  assert.equal(resolvers.length, 2)
  resolvers[0]({ size: 1 }); resolvers[1]({ size: 1 })
  await Promise.all([first, second])
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(resolvers.length, 3)
  resolvers[2]({ size: 1 }); await third
  cache.dispose()
})

test('LRU eviction preserves current page and disposal revokes URLs', async () => {
  const { cache, revoked } = harness(async () => ({ size: 10 }), { maxPages: 2 })
  const first = await cache.get(1)
  const second = await cache.get(2)
  await cache.get(3)
  assert.equal(cache.peek(1), first)
  assert.equal(cache.peek(2), null)
  assert.ok(revoked.includes(second))
  cache.dispose()
  assert.equal(revoked.length, 3)
})

test('failed page can retry and report switching cancels pending requests', async () => {
  let attempts = 0, signal
  const { cache } = harness(async (_, s) => {
    signal = s
    if (++attempts === 1) throw new Error('network')
    return { size: 1 }
  })
  await assert.rejects(cache.get(1))
  await new Promise(resolve => setImmediate(resolve))
  assert.ok(await cache.get(1))
  cache.dispose()
  assert.equal(cache.peek(1), null)
  await assert.rejects(cache.get(1))
  const pending = harness((_, s) => { signal = s; return new Promise(() => {}) }).cache
  const request = pending.get(1)
  await Promise.resolve()
  pending.dispose()
  await assert.rejects(request)
  assert.equal(signal.aborted, true)
})
