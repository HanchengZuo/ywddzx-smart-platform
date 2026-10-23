// Keep tab changes inside the workspace; scrollIntoView also scrolls the browser document.
export function scrollScheduleToFilters(panel) {
  const content = panel?.closest('.content')
  if (!content) return
  const panelTop = panel.getBoundingClientRect().top
  const contentTop = content.getBoundingClientRect().top + content.clientTop
  const offset = Number.parseFloat(getComputedStyle(panel).scrollMarginTop) || 0
  content.scrollTo({ top: Math.max(0, content.scrollTop + panelTop - contentTop - offset) })
}
