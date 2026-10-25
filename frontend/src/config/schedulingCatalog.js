export const schedulingMenuPages = [
  {
    key: 'scheduling-map',
    path: '/inspection/scheduling-map',
    permission: 'view_scheduling_map',
    title: '排班地图',
    icon: '排',
    description: '现场按季度、视频按月，快速查找没有巡检记录的站点。',
  },
  {
    key: 'driving-data',
    // Preserve existing links and global visibility settings after moving menus.
    path: '/management/driving-matrix',
    permission: 'view_driving_matrix',
    title: '路网数据',
    icon: '路',
    description: '查看站间驾车用时、行驶距离及每周采集情况，为智能排班提供依据。',
  },
  {
    key: 'staff-availability',
    path: '/inspection/staff-availability',
    permission: 'view_staff_availability',
    title: '人员档期',
    icon: '档',
    description: '按官方工作日管理人员有空与没空状态，查看历史现场、视频巡检。',
  },
  {
    key: 'inspection-plan',
    path: '/inspection/plan',
    permission: 'view_inspection_schedule',
    title: '巡检排班',
    icon: '班',
    description: '现场按季度、视频按月，在排班表分配检查人并查看逐表检查记录。',
  },
]
