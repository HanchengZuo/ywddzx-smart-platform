import test from 'node:test'
import assert from 'node:assert/strict'
import { createAdaptivePolling } from '../src/utils/adaptivePolling.js'

function fixture(task, canRun) {
  let next, delay
  const polling = createAdaptivePolling({
    task,
    canRun,
    setTimer: (callback, ms) => {
      next = callback
      delay = ms
      return 1
    },
    clearTimer: () => {
      next = undefined
    },
  })
  return {
    polling,
    delay: () => delay,
    scheduled: () => !!next,
    fire: () => {
      const callback = next
      next = undefined
      return callback?.()
    },
  }
}
test('polls once a minute and never overlaps slow requests', async () => {
  let finish,
    calls = 0
  const f = fixture(() => {
    calls++
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  f.polling.start()
  assert.equal(f.delay(), 60000)
  const pending = f.fire()
  f.polling.start({ immediate: true })
  assert.equal(f.scheduled(), false)
  assert.equal(calls, 1)
  finish()
  await pending
  assert.equal(f.delay(), 60000)
  assert.equal(f.scheduled(), true)
})
test('backoff caps at five minutes and successful refresh resets it', async () => {
  let fail = true
  const f = fixture(async () => {
    if (fail) throw new Error('offline')
  })
  f.polling.start()
  for (const delay of [120000, 240000, 300000, 300000]) {
    await f.fire()
    assert.equal(f.delay(), delay)
  }
  fail = false
  await f.fire()
  assert.equal(f.delay(), 60000)
})
test('hidden/offline pauses, resume refreshes immediately, disposal prevents future work', async () => {
  let visible = true,
    calls = 0
  const f = fixture(
    async () => {
      calls++
    },
    () => visible,
  )
  f.polling.start()
  visible = false
  await f.fire()
  assert.equal(calls, 0)
  assert.equal(f.scheduled(), false)
  f.polling.pause()
  visible = true
  f.polling.start({ immediate: true })
  assert.equal(f.delay(), 0)
  await f.fire()
  assert.equal(calls, 1)
  f.polling.dispose()
  f.polling.start({ immediate: true })
  assert.equal(f.scheduled(), false)
})
test('unmount during an in-flight refresh does not reschedule', async () => {
  let finish
  const f = fixture(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  f.polling.start()
  const pending = f.fire()
  f.polling.dispose()
  finish()
  await pending
  assert.equal(f.scheduled(), false)
})
