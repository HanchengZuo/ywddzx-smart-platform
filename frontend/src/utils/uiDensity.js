// Keep desktop density separate from mobile and standalone/printed documents.
export const DESKTOP_DENSITY = 0.8
export const COMPACT_DENSITY_MEDIA = 'screen and (min-width: 769px)'
// `not` negates the complete query, including fractional widths during zoom.
export const REGULAR_DENSITY_MEDIA = `not ${COMPACT_DENSITY_MEDIA}`

// Production CSS minification may rewrite min/max-width to range syntax.
export function densityMediaMode(condition) {
  const normalize = value => String(value).toLowerCase().replace(/\s+/g, '')
    .replace(/\(width<=(\d+)px\)/g, '(max-width:$1px)')
    .replace(/\(width>=(\d+)px\)/g, '(min-width:$1px)')
  const media = normalize(condition)
  if (media === normalize(COMPACT_DENSITY_MEDIA)) return 'compact'
  if (media === normalize(REGULAR_DENSITY_MEDIA)) return 'regular'
  return null
}
