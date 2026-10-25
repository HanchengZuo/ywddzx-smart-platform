const colors = ['#256c9b', '#258477', '#a87b2c', '#676aa4', '#a35d4f', '#357f91']

export function distributionRows(items = []) {
  const source = Array.isArray(items) ? items : []
  const count = value => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0
  const total = source.reduce((sum, item) => sum + count(item.count), 0)
  return source.map((item, index) => {
    const value = count(item.count)
    const supplied = item.percentage !== null && item.percentage !== undefined && item.percentage !== ''
    const percentage = supplied && Number.isFinite(Number(item.percentage)) ? Number(item.percentage) : (total ? value / total * 100 : 0)
    return { ...item, name: item.display_name || item.name || '未命名类别', count: value,
      percentage: Math.max(0, Math.min(100, percentage)), color: colors[index % colors.length] }
  })
}
