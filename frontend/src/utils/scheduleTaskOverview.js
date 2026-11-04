export const taskBuckets = [
  { key: 'today_offline', label: '今日现场', tone: 'field' },
  { key: 'today_online', label: '今日视频', tone: 'video' },
  { key: 'history_offline', label: '历史现场', tone: 'field' },
  { key: 'history_online', label: '历史视频', tone: 'video' },
]

export function bucketCounts(person, key = 'all') {
  const keys = key === 'all' ? taskBuckets.map(bucket => bucket.key) : [key]
  return keys.reduce((counts, bucket) => {
    for (const field of Object.keys(counts)) counts[field] += person.buckets?.[bucket]?.[field] ?? 0
    return counts
  }, { total: 0, pending: 0, completed: 0, exempted: 0 })
}

export function filterPeople(people, { keyword, bucket, state }) {
  const query = keyword.trim().toLocaleLowerCase()
  return people.filter(person => person.name.toLocaleLowerCase().includes(query))
    .map(person => ({ ...person, counts: bucketCounts(person, bucket) }))
    .filter(({ counts }) => state === 'pending' ? counts.pending > 0
      : state === 'clear' ? counts.pending === 0 : true)
    .sort((a, b) => b.counts.pending - a.counts.pending || b.counts.total - a.counts.total
      || a.name.localeCompare(b.name, 'zh-CN') || a.id - b.id)
}

export function overviewMetrics(people) {
  const result = { people: people.length, pendingPeople: 0, todayPending: 0, todayCompleted: 0,
    todayExempted: 0, historyPending: 0, historyOffline: 0, historyOnline: 0 }
  for (const person of people) {
    const field = bucketCounts(person, 'today_offline')
    const video = bucketCounts(person, 'today_online')
    const historyField = bucketCounts(person, 'history_offline').pending
    const historyVideo = bucketCounts(person, 'history_online').pending
    const pending = field.pending + video.pending
    result.todayPending += pending
    result.todayCompleted += field.completed + video.completed
    result.todayExempted += field.exempted + video.exempted
    result.historyOffline += historyField
    result.historyOnline += historyVideo
    result.historyPending += historyField + historyVideo
    if (pending + historyField + historyVideo) result.pendingPeople += 1
  }
  return result
}
