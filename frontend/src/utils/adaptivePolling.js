// Schedule after completion rather than using setInterval so slow requests never pile up.
export function createAdaptivePolling({
  task,
  canRun = () => true,
  interval = 60000,
  maxDelay = 300000,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
}) {
  let timer,
    running = false,
    active = false,
    disposed = false,
    failures = 0
  function schedule(delay) {
    clearTimer(timer)
    if (active && !disposed && canRun()) timer = setTimer(run, delay)
  }
  async function run() {
    timer = undefined
    if (!active || disposed || running || !canRun()) return
    running = true
    try {
      await task()
      failures = 0
    } catch {
      failures = Math.min(failures + 1, 8)
    } finally {
      running = false
      schedule(Math.min(maxDelay, interval * 2 ** failures))
    }
  }
  return {
    start({ immediate = false } = {}) {
      if (disposed) return
      active = true
      if (!running) schedule(immediate ? 0 : interval)
    },
    pause() {
      active = false
      clearTimer(timer)
    },
    dispose() {
      disposed = true
      active = false
      clearTimer(timer)
    },
  }
}
