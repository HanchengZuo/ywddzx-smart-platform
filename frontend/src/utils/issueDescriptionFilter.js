export const parseDescriptionKeywords = (value) => {
  const seen = new Set()
  return String(value || '')
    .trim()
    .split(/[\s,，;；、]+/u)
    .filter((keyword) => {
      const normalized = keyword.toLowerCase()
      if (!keyword || seen.has(normalized)) return false
      seen.add(normalized)
      return true
    })
}

export const descriptionFilterError = (value) => {
  if ([...String(value || '').trim()].length > 1000) return '问题描述搜索最多输入1000个字符。'
  if (parseDescriptionKeywords(value).length > 20) return '问题描述搜索最多使用20个不同关键词。'
  return ''
}

export const describeDescriptionFilter = (source) => {
  const keywords = parseDescriptionKeywords(source.issueDescription)
  if (!keywords.length) return ''
  return `${source.descriptionMatch === 'any' ? '任一包含' : '全部包含'}：${keywords.join('、')}`
}
