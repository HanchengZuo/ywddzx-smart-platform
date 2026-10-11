export const auditProgress = (summary) =>
  summary?.total ? (summary.reviewed / summary.total) * 100 : 0

export function intakeMetrics(data) {
  if (!data) return []
  const s = data.summary,
    r = data.records,
    h = data.highlight_summary
  return [
    {
      label: '巡检触达站点',
      value: r ? r.stations : '—',
      unit: '座',
      hint: r ? `底层巡检记录 ${r.records} 条 · 含零问题巡检` : '无巡检记录查看权限',
      tone: 'cyan',
    },
    {
      label: '已登记问题',
      value: s.total,
      unit: '项',
      hint: `包含待审核 · 已否决/销毁 ${s.destroyed} 项`,
      tone: 'cyan',
    },
    {
      label: '待审核登记',
      value: s.pending_audit,
      unit: '项',
      hint: '待集中审核的发现线索 · 非确认问题',
      tone: 'amber',
    },
    {
      label: '有问题站点',
      value: s.discovery_stations,
      unit: '座',
      hint: `${s.live} 项在库问题 · 含可见待审核登记`,
      tone: 'cyan',
    },
    {
      label: '活跃登记日',
      value: s.active_days,
      unit: '天',
      hint: '所选窗口内有问题登记的自然日',
      tone: 'mint',
    },
    {
      label: '亮点登记',
      value: h.count,
      unit: '项',
      hint: `待审 ${h.pending} · 已确认 ${h.approved} · 已否决 ${h.rejected}`,
      tone: 'mint',
    },
  ]
}
