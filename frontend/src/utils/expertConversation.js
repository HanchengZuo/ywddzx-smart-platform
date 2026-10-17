export const conversationId = (item) => item?.options?.conversation_id || item?.id || ''
export const isExpertPending = (status) => ['queued', 'retrieving', 'answering'].includes(status)

export const groupConversations = (items, keyword = '') => {
  const groups = new Map()
  for (const item of items) {
    const id = conversationId(item)
    if (!groups.has(id)) groups.set(id, { id, items: [], title: '', updatedAt: '', running: false })
    const group = groups.get(id)
    group.items.push(item)
    group.running ||= isExpertPending(item.status)
    if (!group.updatedAt || item.created_at > group.updatedAt) group.updatedAt = item.created_at
    if (item.options?.conversation_title) group.title = item.options.conversation_title
    else if (item.id === id || !group.title) group.title = item.question
  }
  return [...groups.values()]
    .filter((group) => !keyword || group.items.some((item) => item.question.includes(keyword)))
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt) || a.id.localeCompare(b.id))
}

export const citedSources = (result) => {
  const ids = new Set(
    (result?.answer?.paragraphs || []).flatMap((paragraph) => paragraph.sources || []),
  )
  return (result?.sources || []).filter((source) => ids.has(source.id))
}

export const answerText = (item) => {
  const answer = item.result?.answer
  if (!answer) return ''
  const paragraphs = answer.paragraphs.map(
    (part) =>
      (part.title ? part.title + '\n' : '') +
      part.text +
      '\n' +
      (part.sources || []).map((id) => '[' + id + ']').join(' '),
  )
  const sources = citedSources(item.result).map(
    (source) => '[' + source.id + '] ' + source.title + '（' + source.kind + '）',
  )
  return [item.question, ...paragraphs, answer.caveat || '', '回答依据：', ...sources]
    .filter(Boolean)
    .join('\n\n')
}

export const scopeSummary = (options = {}) =>
  [
    options.date_from ? options.date_from + ' 至 ' + options.date_to : '',
    options.region || '',
    ...(options.station_names || []),
  ]
    .filter(Boolean)
    .join(' · ')
