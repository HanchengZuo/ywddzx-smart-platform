export function groupInspectionRecords(records) {
  const groups = new Map()
  for (const record of records) {
    const month = String(record.date || '').slice(0, 7)
    const key = JSON.stringify([record.station_id ?? record.station, month])
    if (!groups.has(key)) {
      groups.set(key, {
        batchKey: key, date: month, station: record.station, records: [],
        batchIssueCount: 0, batchResult: '正常', signedCount: 0, rowspan: 0
      })
    }
    const group = groups.get(key)
    group.records.push(record)
    group.rowspan += 1
    group.batchIssueCount += Number(record.issue_count || 0)
    if (record.result === '异常') group.batchResult = '异常'
    if (record.sign_status === '已签名确认') group.signedCount += 1
  }
  return [...groups.values()]
}
