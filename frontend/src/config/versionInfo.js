import appPackage from '../../package.json'

export const formatAppVersion = (value) => {
  const [major = '1', minor = '0', patch = '0'] = String(value || '1.0').split('.')
  const normalizedMajor = Number.parseInt(major, 10)
  const normalizedMinor = Number.parseInt(minor, 10)
  const normalizedPatch = Number.parseInt(patch, 10)
  const baseVersion = `${Number.isFinite(normalizedMajor) ? normalizedMajor : 1}.${Number.isFinite(normalizedMinor) ? normalizedMinor : 0}`
  return Number.isFinite(normalizedPatch) && normalizedPatch > 0
    ? `${baseVersion}.${normalizedPatch}`
    : baseVersion
}

export const appVersion = formatAppVersion(appPackage.version || '1.0.0')

export const versionHistory = [
  {
    version: 'v1.8.1',
    date: '2026-05-18',
    title: '登记页规范展示可配置',
    summary: '可以自己决定巡检登记搜索规范时显示哪些字段。',
    items: [
      '检查表字段新增“可显示”，登记搜索结果只显示勾选字段。',
      '内部规范字段也新增“可显示”，长内容和显示规则说明更清楚。',
      '优化内部规范字段配置弹窗，选项更好看也更好点。'
    ]
  },
  {
    version: 'v1.8',
    date: '2026-05-16',
    title: '全面升级引入内部规范库',
    summary: '优化巡检规范体系管理体验，并修复数据管理页面偶发死锁问题。',
    items: [
      '原巡检规范库替换成内部规范体系。',
      '添加巡检规范库数据管理，对内部规范增删改查。',
      '原巡检规范库内容迁移至检查表原件库形成外部规范概念，挂在检查表名下。',
      '巡检登记支持在内部规范库和外部规范库之间切换使用。'
    ]
  },
  {
    version: 'v1.7',
    date: '2026-05-14',
    title: 'AI引用巡检规范',
    summary: '巡检登记支持人工引用和AI辅助引用规范。',
    items: [
      '发现问题时可选择人工引用规范或AI引用规范。',
      'AI可根据实际问题描述推荐候选规范，由用户确认引用。'
    ]
  },
  {
    version: 'v1.6.3',
    date: '2026-05-14',
    title: '巡检规范库体验优化',
    summary: '优化规范详情查看方式，并增强分页跳转能力。',
    items: [
      '移动端点击规范后以弹窗查看完整规范详情。',
      '巡检规范库分页支持页码和指定页跳转。'
    ]
  },
  {
    version: 'v1.6.2',
    date: '2026-05-14',
    title: '巡检记录分页与搜索优化',
    summary: '优化巡检记录分页跳转体验，并增强站点名称搜索。',
    items: [
      '巡检记录支持页码跳转，移动端默认每页显示5组记录。',
      '站点筛选支持中文、拼音和拼音首字母匹配。',
      '巡检记录筛选面板新增已签名和待签名筛选。'
    ]
  },
  {
    version: 'v1.6.1',
    date: '2026-05-14',
    title: '巡检登记站点记忆',
    summary: '巡检登记会记住上一次选择的站点，减少重复录入。',
    items: [
      '再次进入或提交后，自动带出上一次选择的站点名称。'
    ]
  },
  {
    version: 'v1.6',
    date: '2026-05-13',
    title: '巡检登记规范索引升级',
    summary: '巡检登记改为直接按规范ID索引，并自动带出所属检查表。',
    items: [
      '取消手动选择检查表流程，减少登记步骤。',
      '选择规范后自动显示规范ID、检查表名称和规范详情。'
    ]
  },
  {
    version: 'v1.5.1',
    date: '2026-05-13',
    title: '巡检规范导出优化',
    summary: '巡检规范库支持按筛选条件导出A4版式文件。',
    items: [
      '筛选后的全部规范可一键生成A4打印页面。',
      '导出内容支持浏览器打印或保存为PDF。'
    ]
  },
  {
    version: 'v1.5',
    date: '2026-05-13',
    title: '检查表字段维护体验升级',
    summary: '优化检查表字段维护体验，支持字段顺序调整和空内容统一展示。',
    items: [
      '检查表字段支持上移、下移、前插和后插，新增字段空值统一显示为“-”。',
      '规范数据编辑时隐藏新增窗口，减少维护过程中的误操作。',
      '规范数据空字段统一以短横线展示，提升数据维护和查看的一致性。'
    ]
  },
  {
    version: 'v1.4',
    date: '2026-05-13',
    title: '巡检记录检查人逻辑优化和检查表签名权限限制',
    summary: '支持多人共同录入同一张检查表，并限制签名确认权限。',
    items: [
      '问题检查人以实际提交账号为准。',
      '巡检记录支持展示多名检查人及每条问题的具体检查人。',
      '检查表签名仅允许实际参与录入的检查人员操作。'
    ]
  },
  {
    version: 'v1.3',
    date: '2026-05-11',
    title: '移动端分页优化',
    summary: '移动端列表增加分页，提升大数据量浏览性能。',
    items: [
      '巡检问题、待办问题和巡检记录移动端统一支持分页。'
    ]
  },
  {
    version: 'v1.2',
    date: '2026-05-11',
    title: '巡检登记搜索优化',
    summary: '优化规范数字搜索，减少误匹配。',
    items: [
      '规范数字搜索改为精准匹配规范ID和检查表内部序号。'
    ]
  },
  {
    version: 'v1.1',
    date: '2026-05-10',
    title: '系统反馈功能准备',
    summary: '新增公共反馈入口，支持问题反馈公开展示与讨论。',
    items: [
      '上线系统反馈提交、截图上传和评论讨论能力。',
      '反馈内容面向所有登录用户公开，便于集中收集和跟进。'
    ]
  },
  {
    version: 'v1.0',
    date: '2026-05-07',
    title: '巡检系统上线发布',
    summary: '首个正式版本聚焦巡检业务闭环，考核系统和培训系统将随后续版本逐步完善。',
    items: [
      '上线巡检登记、问题列表、我的待复核/待整改问题与巡检记录。',
      '上线巡检规范库与检查表原件库，支持规范查询和原始文件查看。',
      '上线巡检计划、站点地图移动端事件流等巡检辅助能力。'
    ]
  }
]
