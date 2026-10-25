// Explain the final station selection, not merely which configuration exists.
export function scheduleBasis(preview) {
  const field = (preview?.groups || []).filter((group) => group.mode === 'offline')
  const meteringCount = new Set(
    field.filter((group) => group.metering_priority).map((group) => group.station_id),
  ).size
  const coverageCount = new Set(
    field.filter((group) => !group.metering_priority).map((group) => group.station_id),
  ).size
  const targets = (preview?.metering_plan?.regions || []).filter((region) => region.target > 0)
  const completed =
    targets.length > 0 && targets.every((region) => region.completed >= region.target)
  const reserved =
    targets.length > 0 &&
    targets.every((region) => region.completed + (region.reserved || 0) >= region.target)
  return {
    metering: {
      applied: meteringCount > 0,
      count: meteringCount,
      label:
        meteringCount > 0
          ? `本次采用 · 优先 ${meteringCount} 站`
          : completed
            ? '本月已完成 · 未采用'
            : !targets.length
              ? '本月无目标 · 未采用'
              : reserved
                ? '计划已预留 · 未采用'
                : '本次未采用',
      detail:
        meteringCount > 0
          ? `本次先选入 ${meteringCount} 个计量优先站点，优先补足当月尚未完成的目标。`
          : completed
            ? '本月计量目标已全部完成，本次无需计量优先选站，转入普通现场片区覆盖均衡。'
            : !targets.length
              ? '本月未配置计量目标，直接按普通现场片区覆盖均衡选站。'
              : reserved
                ? '未完成的计量目标已有保留计划预留，本次没有额外选入计量优先站点。'
                : '本月计量目标尚未完成，但本次没有选入可执行的计量优先站点；请核对人员、可检查站点及方案提示。',
    },
    coverage: {
      applied: coverageCount > 0,
      count: coverageCount,
      label:
        coverageCount > 0
          ? `本次采用 · 均衡 ${coverageCount} 站`
          : meteringCount > 0
            ? '本次仅计量优先 · 未采用'
            : '无现场选站 · 未采用',
      detail:
        coverageCount > 0
          ? meteringCount > 0
            ? `先保留 ${meteringCount} 个计量优先站点，再用剩余名额按片区覆盖均衡选入 ${coverageCount} 站。`
            : `本次 ${coverageCount} 个普通现场站点按片区覆盖均衡选入，再优先组合预计驾车时间短的站点。`
          : meteringCount > 0
            ? '本次现场选站全部用于计量优先任务，没有使用普通片区均衡名额。下方覆盖数据仅供查看。'
            : '本次没有新增现场站点方案，因此未采用片区覆盖均衡选站；视频方案不计入此标识。',
    },
  }
}
