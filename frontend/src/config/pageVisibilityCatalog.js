export const PAGE_VISIBILITY_GROUPS = [
  {
    key: 'map',
    title: '地图中心',
    description: '地图中心相关页面',
    pages: [
      {
        key: '/inspection/station-map',
        path: '/inspection/station-map',
        title: '站点地图',
        description: '查看站点分布、站点状态和地图事件流。'
      }
    ]
  },
  {
    key: 'inspection',
    title: '巡检系统',
    description: '巡检登记、规范、问题、记录、计划和证照页面',
    pages: [
      {
        key: '/inspection/register',
        path: '/inspection/register',
        title: '巡检登记',
        description: '督导人员录入巡检问题或未发现问题记录。'
      },
      {
        key: '/inspection/standards',
        path: '/inspection/standards',
        title: '巡检规范库',
        description: '查看业务督导中心自建的内部巡检规范。'
      },
      {
        key: '/inspection/checklist-originals',
        path: '/inspection/checklist-originals',
        title: '检查表原件库',
        description: '查看检查表 PDF 原件和外部规范列表。'
      },
      {
        key: '/inspection/my-issues',
        path: '/inspection/my-issues',
        title: '我的待复核/待整改问题',
        description: '按账号角色显示待复核或待整改问题。'
      },
      {
        key: '/inspection/issues',
        path: '/inspection/issues',
        title: '巡检问题列表',
        description: '查看、筛选、审核和导出巡检问题。'
      },
      {
        key: '/inspection/records',
        path: '/inspection/records',
        title: '巡检记录',
        description: '查看巡检记录、问题明细和巡检流程状态。'
      },
      {
        key: '/inspection/plan',
        path: '/inspection/plan',
        title: '巡检计划',
        description: '查看巡检计划、派工和完成情况。'
      },
      {
        key: '/inspection/certificates',
        path: '/inspection/certificates',
        title: '证照管理',
        description: '维护和查看站点证照有效期与到期提醒。'
      }
    ]
  },
  {
    key: 'assessment',
    title: '考核系统',
    description: '考核统计、评分和互评页面',
    pages: [
      {
        key: '/assessment',
        path: '/assessment',
        title: '考核系统',
        description: '考核系统入口页面。'
      },
      {
        key: '/assessment/attendance',
        path: '/assessment/attendance',
        title: '人员出勤',
        description: '按检查人统计出勤、记录、问题和站点数量。'
      },
      {
        key: '/assessment/station-score',
        path: '/assessment/station-score',
        title: '站点评分',
        description: '按站点、检查表和时间范围计算评分。'
      },
      {
        key: '/assessment/peer-review',
        path: '/assessment/peer-review',
        title: '成员互评',
        description: '发起、填写和查看成员互评任务。'
      }
    ]
  },
  {
    key: 'training',
    title: '培训系统',
    description: '培训入口和培训材料页面',
    pages: [
      {
        key: '/training',
        path: '/training',
        title: '培训系统',
        description: '督导组内部培训系统入口页面。'
      },
      {
        key: '/training/materials',
        path: '/training/materials',
        title: '培训材料库',
        description: '查看、上传和维护培训 PDF 或视频材料。'
      }
    ]
  },
  {
    key: 'vehicle',
    title: '车辆系统',
    description: '车辆管理相关页面',
    pages: [
      {
        key: '/vehicle',
        path: '/vehicle',
        title: '车辆管理系统',
        description: '车辆管理系统入口页面。'
      }
    ]
  },
  {
    key: 'common',
    title: '公共功能',
    description: '所有用户可用的公共页面',
    pages: [
      {
        key: '/feedback',
        path: '/feedback',
        title: '系统反馈',
        description: '提交反馈、查看反馈广场和参与讨论。'
      }
    ]
  },
  {
    key: 'management',
    title: '管理系统',
    description: '后台管理页面',
    pages: [
      {
        key: '/management/users',
        path: '/management/users',
        title: '用户数据管理',
        description: '管理用户、角色权限、生日信息和账号数据。'
      },
      {
        key: '/management/stations',
        path: '/management/stations',
        title: '站点数据管理',
        description: '维护站点主数据、导入导出和站点账号密码。'
      },
      {
        key: '/management/checklists',
        path: '/management/checklists',
        title: '检查表数据管理',
        description: '维护外部检查表、字段结构和外部规范数据。'
      },
      {
        key: '/management/internal-standards',
        path: '/management/internal-standards',
        title: '巡检规范库数据管理',
        description: '维护内部规范内容、标签和外部规范挂载关系。'
      },
      {
        key: '/management/inspection-completion',
        path: '/management/inspection-completion',
        title: '巡检封存管理',
        description: '管理巡检记录确认、封存和周期规则。'
      },
      {
        key: '/management/backups',
        path: '/management/backups',
        title: '数据备份管理',
        description: '管理数据库和上传文件备份。'
      },
      {
        key: '/management/ai-usage',
        path: '/management/ai-usage',
        title: 'AI调用统计',
        description: '查看 DeepSeek AI 调用次数、字符量和估算费用。'
      }
    ]
  }
]

export const PAGE_VISIBILITY_PAGES = PAGE_VISIBILITY_GROUPS.flatMap((group) => (
  group.pages.map((page) => ({
    ...page,
    groupKey: group.key,
    groupTitle: group.title
  }))
))

export const PAGE_VISIBILITY_PAGE_BY_PATH = PAGE_VISIBILITY_PAGES.reduce((result, page) => {
  result[page.path] = page
  return result
}, {})

export const PAGE_VISIBILITY_PAGE_BY_KEY = PAGE_VISIBILITY_PAGES.reduce((result, page) => {
  result[page.key] = page
  return result
}, {})
