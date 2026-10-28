const visibleRows = root => Array.from(root?.querySelectorAll('[data-issue-id]') || [])
  .filter(row => row.getClientRects().length)

// Capture the actual list viewport, not the fixed review drawer's scroll position.
export function captureIssueListPosition(root, issueId) {
  const rows = visibleRows(root)
  const index = rows.findIndex(row => row.dataset.issueId === String(issueId))
  if (index < 0) return null
  const current = rows[index]
  const top = current.getBoundingClientRect().top
  const containers = []
  const view = root.ownerDocument.defaultView
  for (let parent = current.parentElement; parent; parent = parent.parentElement) {
    if (/(auto|scroll)/.test(view.getComputedStyle(parent).overflowY)) {
      containers.push({ element: parent, top: parent.scrollTop, left: parent.scrollLeft })
    }
  }
  const documentScroller = root.ownerDocument.scrollingElement
  if (documentScroller && !containers.some(item => item.element === documentScroller)) {
    containers.push({ element: documentScroller, top: documentScroller.scrollTop, left: documentScroller.scrollLeft })
  }
  return {
    containers,
    // The next pending issue takes the submitted card's place. At the end of a
    // page, retain the preceding card; a page clamped by the server uses row one.
    candidates: [
      ...rows.slice(index).map(row => ({ id: row.dataset.issueId, top })),
      ...rows.slice(0, index).reverse().map(row => ({ id: row.dataset.issueId, top: row.getBoundingClientRect().top })),
    ],
    top,
  }
}

export function restoreIssueListPosition(root, position) {
  if (!root?.isConnected || !position) return
  const rows = visibleRows(root)
  const candidate = position.candidates.find(item => rows.some(row => row.dataset.issueId === item.id))
  const anchor = candidate ? rows.find(row => row.dataset.issueId === candidate.id) : rows[0]
  const containers = position.containers.filter(item => item.element.isConnected)
  for (const { element, top, left } of [...containers].reverse()) {
    element.scrollTo({ top, left, behavior: 'instant' })
  }
  const inner = containers[0]
  if (anchor && inner) {
    inner.element.scrollTo({
      top: inner.element.scrollTop + anchor.getBoundingClientRect().top - (candidate?.top ?? position.top),
      left: inner.left,
      behavior: 'instant',
    })
  }
}
