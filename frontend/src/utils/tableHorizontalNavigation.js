export const HORIZONTAL_NAV_HEIGHT = 52

export function horizontalNavigationState({ rect, viewport, scrollWidth, clientWidth, scrollLeft }) {
  const max = Math.max(0, scrollWidth - clientWidth)
  const left = Math.max(rect.left, viewport.left)
  const right = Math.min(rect.right, viewport.right)
  return {
    // Leave the native bottom scrollbar in charge when it is already visible.
    visible: clientWidth > 0 && max > 1 && right - left >= 240
      && Math.max(rect.top, viewport.top) < viewport.bottom - 100
      && rect.bottom > viewport.bottom + 1,
    max,
    value: Math.max(0, Math.min(max, scrollLeft)),
    left,
    top: viewport.bottom - HORIZONTAL_NAV_HEIGHT - 12,
    width: Math.max(0, right - left),
  }
}

export function horizontalNavigationDestination(key, value, max, width) {
  const page = Math.max(80, Math.round(width * 0.8))
  const destinations = { Home: 0, End: max, ArrowLeft: value - 80, ArrowRight: value + 80,
    PageUp: value - page, PageDown: value + page }
  return key in destinations ? Math.max(0, Math.min(max, destinations[key])) : null
}
