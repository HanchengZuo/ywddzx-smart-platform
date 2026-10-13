export const operationsPages = [
  {
    key: 'overview',
    path: '/operations/overview',
    permission: 'view_operations_overview',
    title: '运营驾驶舱',
    icon: '舱',
    description: '一屏掌握巡检采集、审核准备与问题分布，不必等待月底审核。',
  },
  {
    key: 'expert',
    path: '/operations/expert',
    permission: 'view_operations_overview',
    title: '专家问答',
    icon: '问',
    description: '基于全局业务资料和数据库事实，提供带来源的专家问答。',
  },
]

export const operationsMenuPages = [
  operationsPages[0],
  {
    key: 'station-map',
    path: '/inspection/station-map',
    permission: 'view_station_map',
    title: '站点地图',
    icon: '图',
    description: '查看站点分布、站点状态和地图事件流。',
  },
  ...operationsPages.slice(1),
]
