import {
  COMPACT_DENSITY_MEDIA,
  DESKTOP_DENSITY,
  REGULAR_DENSITY_MEDIA,
} from '../src/utils/uiDensity.js'

// Scale authored lengths, not the DOM: pointer coordinates, map tiles, canvas
// measurements, fixed overlays and viewport units stay in browser CSS pixels.
export function compactPixels(value, factor = DESKTOP_DENSITY) {
  return value.replace(
    /("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|url\((?:\\.|[^()"'\\]|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')*\))|(?<![\w#.-])(-?(?:\d*\.)?\d+)px\b/gi,
    (token, literal, number) => literal || `${Number((Number(number) * factor).toFixed(5))}px`,
  )
}

export default function desktopDensity() {
  return {
    postcssPlugin: 'platform-desktop-density',
    OnceExit(root, { AtRule }) {
      if (!root.nodes.length) return
      const regular = new AtRule({ name: 'media', params: REGULAR_DENSITY_MEDIA })
      const compact = new AtRule({ name: 'media', params: COMPACT_DENSITY_MEDIA })
      for (const node of [...root.nodes]) {
        // Imports/charset must remain top-level; Vite resolves CSS imports first.
        if (node.type === 'atrule' && ['charset', 'import'].includes(node.name)) continue
        const copy = node.clone()
        if (copy.type === 'decl') copy.value = compactPixels(copy.value)
        if (copy.type === 'atrule' && ['media', 'container'].includes(copy.name)) {
          copy.params = compactPixels(copy.params)
        }
        copy.walkDecls?.(declaration => { declaration.value = compactPixels(declaration.value) })
        copy.walkAtRules?.(rule => {
          if (['media', 'container'].includes(rule.name)) rule.params = compactPixels(rule.params)
        })
        regular.append(node)
        compact.append(copy)
      }
      root.append(regular, compact)
    },
  }
}
