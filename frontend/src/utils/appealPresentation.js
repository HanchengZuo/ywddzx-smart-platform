export function appealProgressSteps(item, reviewers = []) {
  const ended = ['approved', 'rejected', 'cancelled'].includes(item.status)
  const areaRejected = item.status === 'rejected' && !item.quality_at
  const qualityRejected = item.status === 'rejected' && Boolean(item.quality_at)
  return [
    { title: '站点申诉', state: 'done', label: '已提交', owner: item.station_name,
      handler: `申请人：${item.submitted_name || '历史账号'}`, time: item.created_at, reason: item.reason },
    { title: '片区初审', state: areaRejected ? 'rejected' : item.area_at ? 'done' : ended ? 'waiting' : 'active',
      label: areaRejected ? '初审拒绝' : item.area_at ? '初审通过 · 已转交' : ended ? '流程已结束' : '等待初审',
      owner: item.region || '站点未配置片区', handler: item.area_name ? `审核人：${item.area_name}` : '由所属片区账号审核',
      time: item.area_at, reason: item.area_reason || (ended ? '该阶段未作出审核决定。' : '等待片区核实问题与申诉依据。') },
    { title: '质安部终审', state: qualityRejected ? 'rejected' : item.status === 'approved' ? 'done' : item.status === 'quality_pending' ? 'active' : 'waiting',
      label: qualityRejected ? '终审拒绝 · 恢复整改' : item.status === 'approved' ? '终审通过 · 已销毁' : item.status === 'quality_pending' ? '等待终审' : item.status === 'cancelled' && item.area_at ? '终审已取消' : ended ? '未进入终审' : '等待初审通过',
      owner: '质安部', handler: item.quality_name ? `审核人：${item.quality_name}` : `可审核用户：${reviewers.length ? reviewers.join('、') : '暂无，请联系root配置'}`,
      time: item.quality_at, reason: item.quality_reason || (ended ? '流程已结束，无需继续终审。' : '终审通过则问题已销毁；拒绝则回到站点整改。') }
  ]
}
