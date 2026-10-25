import { densityMediaMode } from './uiDensity.js'

// Export the displayed, saved report, not the mutable workbench or PPT preview.
function standaloneStyles(doc) {
  const readRules = rules => [...rules].map(rule => {
    if (rule.type === 1) {
      const holder = doc.createElement('span')
      holder.style.cssText = rule.style.cssText
      for (const property of [...holder.style]) {
        if (/url\s*\(/i.test(holder.style.getPropertyValue(property))) holder.style.removeProperty(property)
      }
      return `${rule.selectorText}{${holder.style.cssText}}`
    }
    if (rule.type === 4 || rule.type === 12) {
      // Workspace density is not a document format. Preserve the report's
      // original responsive typography in downloaded HTML and print output.
      const density = rule.type === 4 ? densityMediaMode(rule.conditionText) : null
      if (density === 'compact') return ''
      if (density === 'regular') return readRules(rule.cssRules)
      return `@${rule.type === 4 ? 'media' : 'supports'} ${rule.conditionText}{${readRules(rule.cssRules)}}`
    }
    // Do not include font downloads, imports or animations from the application shell.
    return ''
  }).join('\n')
  return [...doc.styleSheets].map(sheet => {
    try { return readRules(sheet.cssRules) } catch { return '' }
  }).join('\n').replace(/</g, '\\3c ')
}

const blobAsDataUrl = blob => new Promise((resolve, reject) => {
  const reader = new FileReader()
  reader.onload = () => resolve(reader.result)
  reader.onerror = () => reject(new Error('报告图片读取失败，请重试。'))
  reader.readAsDataURL(blob)
})

export async function buildReportHtml(element, { title, loadImage }) {
  if (!element) throw new Error('HTML报告尚未显示，请稍后重试。')
  const doc = element.ownerDocument
  const view = doc.defaultView
  const clone = element.cloneNode(true)
  const inherited = view.getComputedStyle(element)
  for (const property of [...inherited]) {
    if (property.startsWith('--') && !/url\s*\(/i.test(inherited.getPropertyValue(property))) {
      clone.style.setProperty(property, inherited.getPropertyValue(property))
    }
  }
  const copies = [clone, ...clone.querySelectorAll('*')]
  for (const copy of copies) {
    for (const property of [...(copy.style || [])]) {
      if (/url\s*\(/i.test(copy.style.getPropertyValue(property))) copy.style.removeProperty(property)
    }
    for (const attribute of [...copy.attributes]) {
      if (/^on/i.test(attribute.name) || ['href', 'srcset', 'contenteditable', 'tabindex'].includes(attribute.name)) {
        copy.removeAttribute(attribute.name)
      }
    }
  }
  // Photo enlargement buttons contain the actual report images; unwrap, do not discard them.
  clone.querySelectorAll('button').forEach(node => node.replaceWith(...node.childNodes))
  clone.querySelectorAll('script, style, link, iframe, object, embed, form, input, select, textarea, .html-contents')
    .forEach(node => node.remove())
  clone.querySelectorAll('details').forEach(node => { node.open = true })
  const cache = new Map()
  // Bound concurrent image requests and reuse duplicated issue photos.
  const pictures = [...clone.querySelectorAll('img')]
  let next = 0
  await Promise.all(Array.from({ length: Math.min(4, pictures.length) }, async () => {
    while (next < pictures.length) {
      const picture = pictures[next++]
      picture.removeAttribute('loading')
      const source = picture.getAttribute('src')
      if (!source) continue
      if (/^data:image\/(png|jpeg|gif|webp);base64,/i.test(source)) continue
      if (/^data:image\/svg\+xml;base64,/i.test(source)) {
        const bytes = Uint8Array.from(view.atob(source.split(',')[1]), c => c.charCodeAt(0))
        picture.src = await rasterizeSvg(new Blob([bytes], { type: 'image/svg+xml' }), view)
        continue
      }
      const url = new URL(source, doc.baseURI)
      if (!['http:', 'https:'].includes(url.protocol) || url.origin !== view.location.origin) {
        throw new Error('报告包含无法安全嵌入的图片，HTML未导出。')
      }
      if (!cache.has(url.href)) {
        cache.set(url.href, Promise.resolve().then(() => loadImage(url.href)).then(blob => {
          if (!/^image\/(png|jpeg|gif|webp|svg\+xml)$/i.test(blob.type)) {
            throw new Error('报告图片加载失败，HTML未导出，请重试。')
          }
          // SVG from the authenticated server is rasterized by the browser before embedding.
          if (blob.type === 'image/svg+xml') return rasterizeSvg(blob, view)
          return blobAsDataUrl(blob)
        }))
      }
      picture.src = await cache.get(url.href)
    }
  }))
  clone.style.width = '100%'
  clone.style.maxWidth = '1400px'
  clone.style.margin = '0 auto'
  const output = doc.implementation.createHTMLDocument(String(title || '检查报告'))
  output.documentElement.lang = 'zh-CN'
  const charset = output.createElement('meta')
  charset.setAttribute('charset', 'utf-8')
  output.head.prepend(charset)
  const viewport = output.createElement('meta')
  viewport.name = 'viewport'
  viewport.content = 'width=device-width, initial-scale=1'
  output.head.append(viewport)
  const policy = output.createElement('meta')
  policy.httpEquiv = 'Content-Security-Policy'
  policy.content = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
  output.head.append(policy)
  const style = output.createElement('style')
  // Keep authored responsive rules. Capturing measured pixels freezes lazy images at height zero.
  style.textContent = standaloneStyles(doc) + '\nhtml,body{height:auto!important;overflow:auto!important}body{margin:0;padding:24px;background:#fff}body,body *{font-family:"Microsoft YaHei","SimSun",sans-serif!important}'
  output.head.append(style)
  output.body.append(output.importNode(clone, true))
  return `<!DOCTYPE html>\n${output.documentElement.outerHTML}`
}

async function rasterizeSvg(blob, view) {
  const url = view.URL.createObjectURL(blob)
  try {
    const image = new view.Image()
    image.src = url
    await image.decode()
    const canvas = view.document.createElement('canvas')
    canvas.width = image.naturalWidth || 256
    canvas.height = image.naturalHeight || 256
    canvas.getContext('2d').drawImage(image, 0, 0)
    return canvas.toDataURL('image/png')
  } finally {
    view.URL.revokeObjectURL(url)
  }
}

export async function downloadReportHtml(element, options) {
  const html = await buildReportHtml(element, options)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = String(options.filename || '检查报告.html').replace(/[\\/:*?"<>|]/g, '_')
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => window.URL.revokeObjectURL(url), 60000)
}
