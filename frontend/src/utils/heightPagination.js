// Use measured card heights to fill a column without clipping text. An oversized
// card owns a page so even unusually long standards remain readable.
export function paginateByHeight(heights, availableHeight, gap = 12) {
  const budget = Number.isFinite(availableHeight) ? Math.max(1, availableHeight) : 1
  const spacing = Number.isFinite(gap) ? Math.max(0, gap) : 0
  const pages = []
  let start = 0, used = 0
  for (let index = 0; index < heights.length; index++) {
    const height = Number.isFinite(heights[index]) && heights[index] > 0 ? heights[index] : 160
    const next = used + (index > start ? spacing : 0) + height
    if (index > start && next > budget) {
      pages.push({ start, end: index })
      start = index
      used = height
    } else used = next
  }
  if (start < heights.length) pages.push({ start, end: heights.length })
  return pages
}
