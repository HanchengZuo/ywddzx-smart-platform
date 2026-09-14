// Aborting is best-effort; identity checks also reject responses already in flight.
export const createLatestRequest = () => {
  let current = null
  const cancel = () => {
    current?.abort()
    current = null
  }
  return {
    cancel,
    start() {
      cancel()
      const controller = new AbortController()
      current = controller
      return { signal: controller.signal, isCurrent: () => current === controller && !controller.signal.aborted }
    }
  }
}
