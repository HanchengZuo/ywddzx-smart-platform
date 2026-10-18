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
    if (heading) blocks.push({ type: 'heading', text: heading[1], id: `section-${blocks.length}` })
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
