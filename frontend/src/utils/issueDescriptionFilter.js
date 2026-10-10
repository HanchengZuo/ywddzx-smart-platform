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
