export function parseHelpBody(body = '') {
  const blocks = []
  for (const line of body.replace(/\r\n?/g, '\n').split('\n')) {
    if (!line.trim()) {
      blocks.push({ type: 'gap' })
      continue
    }
    const heading = line.match(/^#{1,3}\s+(.+)$/)
    const step = line.match(/^\d+[.、]\s*(.+)$/)
    const bullet = line.match(/^[-*]\s+(.+)$/)
    const note = line.match(/^>\s*(.+)$/)
    const image = parseHelpImage(line)
    if (image) blocks.push({ type: 'image', ...image })
    else if (heading)
      blocks.push({ type: 'heading', text: heading[1], id: `section-${blocks.length}` })
    else if (step || bullet) {
      const type = step ? 'steps' : 'list'
      if (blocks.at(-1)?.type !== type) blocks.push({ type, items: [] })
      blocks.at(-1).items.push((step || bullet)[1])
    } else if (note) blocks.push({ type: 'note', text: note[1] })
    else if (blocks.at(-1)?.type === 'paragraph') blocks.at(-1).text += '\n' + line
    else blocks.push({ type: 'paragraph', text: line })
  }
  return blocks.filter((block) => block.type !== 'gap')
}

export function parseHelpImage(line) {
  if (!line.startsWith('::help-image ')) return null
  try {
    const node = JSON.parse(line.slice('::help-image '.length))
    if (
      typeof node.id !== 'string' ||
      !/^[a-z0-9-]{1,80}$/.test(node.id) ||
      typeof (node.caption ?? '') !== 'string' ||
      (node.caption || '').length > 160 ||
      ![50, 75, 100].includes(node.width ?? 100)
    )
      return null
    return { assetId: node.id, caption: node.caption || '', width: node.width || 100 }
  } catch {
    return null
  }
}

export function serializeHelpBlocks(blocks) {
  return blocks
    .map((block) => {
      if (block.type === 'image')
        return (
          '::help-image ' +
          JSON.stringify({
            id: block.assetId,
            caption: block.caption || '',
            width: block.width || 100,
          })
        )
      if (block.type === 'heading') return '## ' + block.text
      if (block.type === 'note') return '> ' + block.text
      if (block.type === 'steps')
        return block.items.map((item, index) => `${index + 1}. ${item}`).join('\n')
      if (block.type === 'list') return block.items.map((item) => '- ' + item).join('\n')
      return block.text || ''
    })
    .join('\n\n')
}

export function inlineLegacyImages(content, images) {
  const blocks = parseHelpBody(content.body || '')
  const present = new Set(
    blocks.filter((block) => block.type === 'image').map((block) => block.assetId),
  )
  for (const id of content.attachments || []) {
    const image = images.find((item) => item.id === id)
    if (image && !present.has(id)) {
      blocks.push({ type: 'image', assetId: id, caption: image.title, width: 100 })
      present.add(id)
    }
  }
  return serializeHelpBlocks(blocks)
}

export const helpStatus = (item) =>
  item.archived
    ? '已下架'
    : !item.published_at
      ? '未发布草稿'
      : item.has_draft
        ? '有未发布修改'
        : '已发布'
export const blankHelpContent = () => ({
  title: '',
  category: '新手上手',
  summary: '',
  body: '',
  tags: [],
  attachments: [],
})
export function filterHelpArticles(items, keyword, category = '') {
  const terms = keyword.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean)
  return items.filter(
    (item) =>
      (!category || item.content.category === category) &&
      terms.every((term) =>
        [item.content.title, item.content.summary, item.content.body, ...(item.content.tags || [])]
          .join(' ')
          .toLocaleLowerCase()
          .includes(term),
      ),
  )
}
