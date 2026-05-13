const normalizeMultiline = (value) => String(value || '').replace(/\\n/g, '\n')

const parseDetailLine = (line) => {
    const text = String(line || '').trim()
    const fullWidthIndex = text.indexOf('：')
    const rawHalfWidthIndex = text.indexOf(':')
    const halfWidthIndex = rawHalfWidthIndex > -1 && text[rawHalfWidthIndex + 1] !== '/'
        ? rawHalfWidthIndex
        : -1
    const separatorIndex = fullWidthIndex > -1
        ? fullWidthIndex
        : halfWidthIndex

    if (separatorIndex < 0) return null

    const label = text.slice(0, separatorIndex).trim()
    if (!label || label.length > 48) return null

    return {
        label,
        value: text.slice(separatorIndex + 1).trim()
    }
}

export const formatStandardDetailText = (value) => normalizeMultiline(value)

export const parseStandardDetailText = (value) => {
    const entries = []

    normalizeMultiline(value)
        .split('\n')
        .map((line) => String(line || '').trim())
        .filter(Boolean)
        .forEach((line) => {
            const parsed = parseDetailLine(line)

            if (parsed) {
                entries.push({
                    key: `detail_${entries.length}`,
                    label: parsed.label,
                    value: parsed.value || '-'
                })
                return
            }

            if (entries.length > 0) {
                const lastEntry = entries[entries.length - 1]
                lastEntry.value = `${lastEntry.value}\n${line}`.trim()
                return
            }

            entries.push({
                key: `detail_${entries.length}`,
                label: '规范内容',
                value: line
            })
        })

    return entries
}

export const getStandardDetailPreview = (value, limit = 3) => {
    const entries = parseStandardDetailText(value)
    if (!entries.length) return '暂无规范详情'

    return entries
        .slice(0, limit)
        .map((entry) => `${entry.label}：${entry.value || '-'}`)
        .join('\n')
}
