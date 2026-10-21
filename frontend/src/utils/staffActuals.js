export function actualsRefreshDelay(metadata) {
  if (!metadata?.actuals_pending) return null
  const cutoff = Date.parse(metadata.actuals_release_at)
  const server = Date.parse(metadata.server_now)
  if (!Number.isFinite(cutoff) || !Number.isFinite(server)) return null
  // Use server time, not the operator's computer clock; let the boundary pass before reading again.
  return Math.min(2147483647, Math.max(100, cutoff - server + 100))
}
