import { operationsMenuPages } from './operationsCatalog.js'
import { schedulingMenuPages } from './schedulingCatalog.js'

export const PAGE_VISIBILITY_GROUPS = [
  {
    key: 'map',
    title: '运营系统',
    description: '运营驾驶舱、站点地图和专家问答',
    pages: operationsMenuPages.map(page => ({ key: page.path, path: page.path, title: page.title, description: page.description }))
  },
  {
    key: 'inspection',
    title: '巡检系统',
    description: '巡检登记、规范、问题、记录和证照页面',
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
        key: '/inspection/highlights',
        path: '/inspection/highlights',
        title: '亮点列表',
        description: '独立展示及审核亮点，沿用巡检问题的数据范围与审核权限。'
      },
      {
        key: '/inspection/records',
        path: '/inspection/records',
        title: '巡检记录',
        description: '查看巡检记录、问题明细和巡检流程状态。'
      },
      {
        key: '/inspection/certificates',
        path: '/inspection/certificates',
        title: '证照管理',
        description: '维护和查看站点证照有效期与到期提醒。'
      },
      {
        key: '/inspection/appeals',
        path: '/inspection/appeals',
        title: '申诉空间',
        description: '所有用户可访问，按数据范围查看站点申诉；片区初审、授权质安部终审。'
      }
    ]
  },
  {
    key: 'scheduling',
    title: '排班系统',
    description: '排班地图、路网数据、人员档期与巡检排班',
    pages: schedulingMenuPages.map(page => ({ key: page.path, path: page.path, title: page.title, description: page.description }))
  },
  {
    key: 'ai',
    title: 'AI系统',
    description: 'AI报告生成相关页面',
    pages: [
      {
        key: '/inspection/reports',
        path: '/inspection/reports',
        title: '报告生成',
        description: '按月份汇总巡检数据并调用AI生成监督检查报告。'
      }
    ]
  },
  {
    key: 'assessment',
    title: '考核系统',
    description: '考核统计和站点评分页面',
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
        description: '按站点、可评分检查表及自然月核对审核通过的问题。'
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
        key: '/help-documents',
        path: '/help-documents',
        title: '帮助文档',
        description: '所有用户可阅读使用指南，获得编辑权限的用户可维护内容。'
      },
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
        key: '/management/security',
        path: '/management/security',
        title: '系统安全管理',
        description: '识别账号风险、维护密码策略并查看安全操作记录。'
      },
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
        key: '/management/quality-deadlines',
        path: '/management/quality-deadlines',
        title: '质安流程时限管理',
        description: '配置指定五张检查表的验收、申诉时限，追溯超时处理。'
      },
      {
        key: '/management/auto-audit',
        path: '/management/auto-audit',
        title: '白名单自动审核管理',
        description: '配置巡检问题自动通过、否决规则并回溯命中记录。'
      },
      {
        key: '/management/backups',
        path: '/management/backups',
        title: '数据备份管理',
        description: '管理数据库和上传文件备份。'
      },
      {
        key: '/management/ai-models',
        path: '/management/ai-models',
        title: '大模型管理',
        description: '统一或按调用场景切换大模型厂家与型号。'
      },
      {
        key: '/management/notifications',
        path: '/management/notifications',
        title: '消息通知管理',
        description: '管理浏览器推送订阅、用户开通情况和消息发送记录。'
      },
      {
        key: '/management/ai-usage',
        path: '/management/ai-usage',
        title: 'AI调用统计',
        description: '查看各模型 AI 调用次数、字符量和估算用量。'
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
