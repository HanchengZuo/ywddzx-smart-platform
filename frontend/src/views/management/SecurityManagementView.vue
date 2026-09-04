<template>
  <div class="security-page">
    <section class="security-hero">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>系统安全管理</h2>
        <p>集中识别账号密码风险、维护统一策略，并通过安全审计追踪每一次敏感操作。</p>
      </div>
      <div class="mode-panel" :class="policy.enforcement_mode">
        <span>{{ policy.enforcement_mode === 'enforce' ? '正式执行' : '观察模式' }}</span>
        <strong>{{ policy.enforcement_mode === 'enforce' ? '强制改密限制已生效' : '仅识别风险，不拦截登录' }}</strong>
      </div>
    </section>

    <nav class="security-tabs" aria-label="系统安全管理页签">
      <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)">
        <span>{{ tab.icon }}</span>
        <strong>{{ tab.label }}</strong>
      </button>
    </nav>

    <div v-if="toast.text" class="security-toast" :class="toast.type">{{ toast.text }}</div>

    <template v-if="activeTab === 'accounts'">
      <section class="stats-grid">
        <article v-for="card in statCards" :key="card.key" :class="['stat-card', card.key]">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <small>{{ card.help }}</small>
        </article>
      </section>

      <section class="security-card filter-card">
        <div class="section-heading compact">
          <div>
            <span>账号筛选</span>
            <h3>快速定位风险账号</h3>
            <p>支持账号模糊搜索与多条件组合筛选，查询结果可直接用于批量安全处理。</p>
          </div>
          <div class="filter-actions">
            <button class="btn btn-secondary" type="button" @click="resetFilters">重置</button>
            <button class="btn btn-primary" type="button" :disabled="accountsLoading" @click="applyFilters">
              {{ accountsLoading ? '查询中...' : '查询账号' }}
            </button>
          </div>
        </div>

        <div class="account-search-row">
          <label class="keyword-field search-field">
            <span>搜索账号</span>
            <div class="search-control">
              <i aria-hidden="true">搜</i>
              <input v-model.trim="filters.keyword" placeholder="输入用户名、姓名、站点或片区"
                @keyup.enter="applyFilters" />
              <button v-if="filters.keyword" type="button" aria-label="清空搜索内容"
                @click="filters.keyword = ''">×</button>
            </div>
          </label>
          <div class="quick-filter-group">
            <span>快捷筛选</span>
            <div>
              <button type="button" :class="{ active: filters.risk_level === 'high_risk' }"
                @click="applyQuickFilter('risk_level', 'high_risk')">高风险账号</button>
              <button type="button" :class="{ active: filters.must_change_password === 'true' }"
                @click="applyQuickFilter('must_change_password', 'true')">待强制改密</button>
              <button type="button" :class="{ active: filters.account_status === 'suspended' }"
                @click="applyQuickFilter('account_status', 'suspended')">已暂停账号</button>
            </div>
          </div>
        </div>

        <div class="filter-grid">
          <label>
            <span>角色</span>
            <select v-model="filters.role"><option value="">全部角色</option><option v-for="item in options.roles" :key="item.value" :value="item.value">{{ item.label }}</option></select>
          </label>
          <label>
            <span>所属片区</span>
            <select v-model="filters.station_region" @change="handleRegionChange"><option value="">全部片区</option><option v-for="region in regionOptions" :key="region" :value="region">{{ region }}</option></select>
          </label>
          <label>
            <span>所属站点</span>
            <select v-model="filters.station_id"><option value="">全部站点</option><option v-for="item in filteredStationOptions" :key="item.id" :value="String(item.id)">{{ item.region ? `${item.region} · ` : '' }}{{ item.station_name }}</option></select>
          </label>
          <label>
            <span>风险等级</span>
            <select v-model="filters.risk_level"><option value="">全部风险</option><option value="high_risk">严重 + 高风险</option><option v-for="item in options.risk_levels" :key="item.value" :value="item.value">{{ item.label }}</option></select>
          </label>
          <label>
            <span>强制改密状态</span>
            <select v-model="filters.must_change_password"><option value="">全部改密状态</option><option value="true">待强制改密</option><option value="false">无需强制改密</option></select>
          </label>
          <label>
            <span>账号状态</span>
            <select v-model="filters.account_status"><option value="">全部状态</option><option value="active">正常</option><option value="suspended">已暂停</option></select>
          </label>
          <label>
            <span>Passkey状态</span>
            <select v-model="filters.passkey_status"><option value="">全部绑定状态</option><option value="bound">已绑定Passkey</option><option value="unbound">未绑定Passkey</option></select>
          </label>
        </div>

        <div v-if="appliedFilterChips.length" class="applied-filter-strip">
          <span class="applied-filter-title">当前条件</span>
          <button v-for="item in appliedFilterChips" :key="item.key" type="button"
            :title="`移除${item.label}筛选`" @click="removeAppliedFilter(item.key)">
            <small>{{ item.label }}</small><strong>{{ item.value }}</strong><b>×</b>
          </button>
          <span class="applied-filter-count">筛得 {{ pagination.total }} 个账号</span>
        </div>
      </section>

      <section class="security-card accounts-card">
        <div class="section-heading">
          <div>
            <span>账号密码安全</span>
            <h3>账号风险清单</h3>
            <p>当前筛选结果 {{ pagination.total }} 个账号，可在清单中查看风险并管理单个账号。</p>
          </div>
          <div class="account-batch-actions">
            <button class="btn initialize-button" type="button" :disabled="accountsLoading || !stats.total" @click="openInitializationDialog">
              所有用户一键初始化为强密码并导出 Excel
            </button>
          </div>
        </div>

        <div v-if="accountsLoading" class="state-panel"><span class="loading-ring"></span><strong>正在读取账号安全状态</strong></div>
        <div v-else-if="!accounts.length" class="state-panel empty"><strong>当前没有符合条件的账号</strong><span>可调整筛选条件后重新查询。</span></div>
        <div v-else class="account-table-wrap">
          <div class="account-table account-table-head">
            <div>用户名 / 姓名</div><div>角色</div><div>所属站点</div><div>风险等级与原因</div>
            <div>登录方式</div><div>必须改密</div><div>最后改密</div><div>账号状态</div><div>操作</div>
          </div>
          <article v-for="account in accounts" :key="account.id" class="account-table account-row">
            <div data-label="账号"><strong>{{ account.username }}</strong><small>{{ account.real_name || '-' }}</small></div>
            <div data-label="角色"><span class="role-chip">{{ account.role_label }}</span></div>
            <div data-label="所属站点"><strong>{{ account.station_name || '-' }}</strong><small>{{ account.station_region || '未关联站点' }}</small></div>
            <div data-label="风险"><span :class="['risk-chip', account.risk_level]">{{ account.risk_label }}</span><small class="risk-reason">{{ account.risk_reasons.join('；') }}</small></div>
            <div data-label="登录方式"><span :class="['login-method-chip', { passkey: account.passkey_bound }]">{{ account.login_method_label }}</span><small v-if="account.passkey_count">{{ account.passkey_count }} 个凭据</small></div>
            <div data-label="必须改密"><span :class="['boolean-chip', { active: account.must_change_password }]">{{ account.must_change_password ? (account.force_change_immediately ? '立即执行' : '是') : '否' }}</span></div>
            <div data-label="最后改密"><span class="date-text">{{ account.password_changed_at }}</span></div>
            <div data-label="账号状态"><span :class="['status-chip', account.account_status]">{{ account.account_status_label }}</span></div>
            <div class="account-actions" data-label="操作">
              <button type="button" @click="runAccountAction(account, account.must_change_password ? 'cancel_force_change' : 'force_change')">{{ account.must_change_password ? '取消改密' : '强制改密' }}</button>
              <button v-if="account.risk_level === 'critical' && account.id !== currentUserId" type="button" class="danger-outline" @click="openImmediateDialog(account)">立即执行</button>
              <button type="button" @click="runAccountAction(account, 'invalidate_sessions')">注销会话</button>
              <button v-if="account.role !== 'root'" type="button" :class="account.account_status === 'active' ? 'danger-outline' : 'restore'" @click="runAccountAction(account, account.account_status === 'active' ? 'suspend' : 'restore')">{{ account.account_status === 'active' ? '暂停' : '恢复' }}</button>
              <button type="button" @click="viewAccountLogs(account)">记录</button>
            </div>
          </article>
        </div>

        <div v-if="pagination.total" class="pagination-bar">
          <span>第 {{ pagination.page }} / {{ pagination.total_pages }} 页，共 {{ pagination.total }} 个账号</span>
          <div><button type="button" :disabled="pagination.page <= 1" @click="loadAccounts(1)">首页</button><button type="button" :disabled="pagination.page <= 1" @click="loadAccounts(pagination.page - 1)">上一页</button><button v-for="page in visiblePages" :key="page" type="button" :class="{ active: page === pagination.page }" @click="loadAccounts(page)">{{ page }}</button><button type="button" :disabled="pagination.page >= pagination.total_pages" @click="loadAccounts(pagination.page + 1)">下一页</button><button type="button" :disabled="pagination.page >= pagination.total_pages" @click="loadAccounts(pagination.total_pages)">末页</button></div>
        </div>
      </section>
    </template>

    <template v-else-if="activeTab === 'policy'">
      <section class="security-card policy-card">
        <div class="section-heading">
          <div><span>密码策略</span><h3>统一密码安全基线</h3><p>规则由后端最终校验，更新规则会生成新策略版本并标记尚未整改的账号。</p></div>
          <div class="policy-meta"><span>当前版本</span><strong>V{{ policy.version || 1 }}</strong><small>{{ policy.updated_by_username ? `${policy.updated_by_username} · ${policy.updated_at}` : '系统默认策略' }}</small></div>
        </div>

        <div class="mode-switch-card">
          <div><strong>执行模式</strong><p>观察模式只展示风险；正式执行后，待强制改密账号只能修改密码或退出登录。</p></div>
          <div class="mode-options"><button type="button" :class="{ active: policyForm.enforcement_mode === 'observe' }" @click="policyForm.enforcement_mode = 'observe'">观察模式</button><button type="button" class="enforce" :class="{ active: policyForm.enforcement_mode === 'enforce' }" @click="policyForm.enforcement_mode = 'enforce'">正式执行</button></div>
        </div>

        <div class="policy-grid">
          <label><span>普通账号最短长度</span><input v-model.number="policyForm.normal_min_length" type="number" min="8" max="64" /><small>建议保持 12 位，后续可逐步提高。</small></label>
          <label><span>高权限账号最短长度</span><input v-model.number="policyForm.privileged_min_length" type="number" min="8" max="64" /><small>适用于 root、supervisor 等账号。</small></label>
          <label><span>最大密码长度</span><input v-model.number="policyForm.max_length" type="number" min="64" max="256" /><small>支持长密码短语，至少为 64 位。</small></label>
          <label><span>禁止重复最近密码</span><input v-model.number="policyForm.history_count" type="number" min="0" max="20" /><small>设置为 0 表示不检查密码历史。</small></label>
          <label><span>整改宽限期（天）</span><input v-model.number="policyForm.grace_period_days" type="number" min="0" max="365" /><small>用于风险整改安排，不做机械定期换密。</small></label>
          <label class="switch-field"><span>必须包含大写字母</span><input v-model="policyForm.require_uppercase" type="checkbox" /><small>至少包含 1 个 A-Z 字母。</small></label>
          <label class="switch-field"><span>必须包含小写字母</span><input v-model="policyForm.require_lowercase" type="checkbox" /><small>至少包含 1 个 a-z 字母。</small></label>
          <label class="switch-field"><span>必须包含数字</span><input v-model="policyForm.require_number" type="checkbox" /><small>至少包含 1 个数字。</small></label>
          <label class="switch-field"><span>必须包含特殊字符</span><input v-model="policyForm.require_special" type="checkbox" /><small>例如 ! @ # $ % 等字符。</small></label>
          <label class="switch-field"><span>修改密码后注销其他会话</span><input v-model="policyForm.logout_other_sessions" type="checkbox" /><small>建议保持开启。</small></label>
          <label class="switch-field"><span>禁止账号关联信息</span><input v-model="policyForm.forbid_identity_similarity" type="checkbox" /><small>阻止用户名、手机号、站点编号等进入密码。</small></label>
          <label class="weak-password-field"><span>弱密码黑名单</span><textarea v-model="policyForm.weak_passwords_text" rows="7" placeholder="每行一个弱密码"></textarea><small>每行一个值；保存和日志中不会记录用户实际密码。</small></label>
        </div>
        <div class="policy-save-bar"><div><strong>保存前需要重新验证当前管理员密码</strong><span>切换为正式执行可能影响大量账号，请先确认风险统计。</span></div><button class="btn btn-primary" type="button" :disabled="policySaving" @click="openPolicyConfirm">{{ policySaving ? '保存中...' : '验证并保存策略' }}</button></div>
      </section>
    </template>

    <template v-else>
      <section class="security-card logs-card">
        <div class="section-heading compact"><div><span>只读审计</span><h3>安全操作记录</h3><p>普通管理员不能编辑或删除，记录不包含任何密码、哈希或临时凭据。</p></div><button v-if="logFilters.target_user_id" class="btn btn-secondary" type="button" @click="clearAccountLogFilter">查看全部记录</button></div>
        <div class="log-filters"><input v-model.trim="logFilters.keyword" placeholder="搜索操作者、目标账号或操作类型" @keyup.enter="loadLogs(1)" /><select v-model="logFilters.action_result"><option value="">全部结果</option><option value="success">成功</option><option value="failure">失败</option></select><button class="btn btn-primary" type="button" @click="loadLogs(1)">查询</button></div>
        <div v-if="logsLoading" class="state-panel"><span class="loading-ring"></span><strong>正在读取安全操作记录</strong></div>
        <div v-else-if="!logs.length" class="state-panel empty"><strong>暂无安全操作记录</strong></div>
        <div v-else class="log-list"><article v-for="item in logs" :key="item.id"><div class="log-time"><strong>{{ item.created_at }}</strong><span :class="['result-chip', item.action_result]">{{ item.action_result === 'success' ? '成功' : '失败' }}</span></div><div class="log-main"><strong>{{ actionLabel(item.action_type) }}</strong><span>{{ item.actor_username }}（{{ item.actor_role }}） → {{ item.target_username || '系统范围' }}</span><small v-if="item.failure_reason">原因：{{ item.failure_reason }}</small></div><div class="log-source"><span>影响 {{ item.affected_count }} 个账号</span><small>{{ item.request_ip || '无来源IP' }}</small></div></article></div>
        <div v-if="logPagination.total" class="pagination-bar"><span>第 {{ logPagination.page }} / {{ logPagination.total_pages }} 页，共 {{ logPagination.total }} 条</span><div><button type="button" :disabled="logPagination.page <= 1" @click="loadLogs(logPagination.page - 1)">上一页</button><button type="button" :disabled="logPagination.page >= logPagination.total_pages" @click="loadLogs(logPagination.page + 1)">下一页</button></div></div>
      </section>
    </template>

    <div v-if="dialog.visible" class="modal-backdrop">
      <section class="confirm-dialog" role="dialog" aria-modal="true">
        <button class="modal-close" type="button" @click="closeDialog">×</button>
        <div class="dialog-mark">盾</div>
        <h3>{{ dialog.title }}</h3>
        <p>{{ dialog.description }}</p>
        <div v-if="dialog.affectedCount !== null" class="impact-panel"><span>预计影响账号</span><strong>{{ dialog.affectedCount }}</strong><small v-if="dialog.highRiskCount">其中高风险账号 {{ dialog.highRiskCount }} 个</small></div>
        <template v-if="dialog.type === 'initialization'">
          <div class="initialization-scope">
            <span v-for="(count, label) in dialog.roleCounts" :key="label"><strong>{{ label }}</strong>{{ count }} 个</span>
          </div>
          <ul class="initialization-warnings">
            <li>内置 root 账号和当前操作账号不会被初始化。</li>
            <li>其他账号的旧密码与已登录会话将立即失效。</li>
            <li>Excel 内的初始密码只生成这一次，系统不保存可查看的明文。</li>
            <li v-if="dialog.suspendedCount">其中 {{ dialog.suspendedCount }} 个已暂停账号会更换密码，但仍保持暂停。</li>
          </ul>
        </template>
        <label v-if="dialog.requirePassword"><span>当前管理员密码</span><input v-model="dialog.currentPassword" type="password" autocomplete="current-password" placeholder="用于确认本次高风险操作" @keyup.enter="confirmDialog" /></label>
        <div class="dialog-actions"><button class="btn btn-secondary" type="button" :disabled="dialog.saving" @click="closeDialog">取消</button><button class="btn btn-danger" type="button" :disabled="dialog.saving || (dialog.requirePassword && !dialog.currentPassword)" @click="confirmDialog">{{ dialog.saving ? '处理中...' : (dialog.type === 'initialization' ? '初始化并下载' : '确认执行') }}</button></div>
      </section>
    </div>

    <div v-if="initialCredentialExporting" class="credential-processing" role="status" aria-live="polite">
      <div class="credential-processing-card">
        <div class="processing-shield"><span></span></div>
        <h3>正在初始化账号密码</h3>
        <p>系统正在逐一生成强密码、写入安全哈希并制作 Excel，请不要关闭页面。</p>
        <div class="processing-line"><span></span></div>
        <small>全部成功后文件会自动下载；任一步失败都会整体回滚。</small>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'

const tabs = [
  { key: 'accounts', label: '账号密码安全', icon: '账' },
  { key: 'policy', label: '密码策略', icon: '策' },
  { key: 'logs', label: '安全操作记录', icon: '录' }
]
const activeTab = ref('accounts')
const accountsLoading = ref(false)
const policySaving = ref(false)
const logsLoading = ref(false)
const initialCredentialExporting = ref(false)
const accounts = ref([])
const logs = ref([])
const currentUserId = Number(localStorage.getItem('user_id') || 0)
const stats = reactive({ total: 0, high_risk: 0, must_change: 0, compliant: 0, disabled: 0 })
const options = reactive({ roles: [], stations: [], risk_levels: [] })
const pagination = reactive({ page: 1, page_size: 10, total: 0, total_pages: 1 })
const logPagination = reactive({ page: 1, page_size: 20, total: 0, total_pages: 1 })
const emptyAccountFilters = () => ({
  keyword: '',
  role: '',
  station_region: '',
  station_id: '',
  risk_level: '',
  must_change_password: '',
  account_status: '',
  passkey_status: ''
})
const filters = reactive(emptyAccountFilters())
const appliedFilters = reactive(emptyAccountFilters())
const logFilters = reactive({ keyword: '', action_result: '', target_user_id: '' })
const policy = reactive({ enforcement_mode: 'observe', version: 1 })
const policyForm = reactive({ enforcement_mode: 'observe', normal_min_length: 12, privileged_min_length: 15, max_length: 64, require_uppercase: true, require_lowercase: true, require_number: true, require_special: true, history_count: 5, grace_period_days: 30, logout_other_sessions: true, forbid_identity_similarity: true, weak_passwords_text: '' })
const toast = reactive({ text: '', type: 'success' })
const dialog = reactive({ visible: false, type: '', title: '', description: '', account: null, requirePassword: false, currentPassword: '', affectedCount: null, highRiskCount: 0, suspendedCount: 0, roleCounts: {}, saving: false })

const statCards = computed(() => [
  { key: 'total', label: '账号总数', value: stats.total, help: '系统当前全部账号' },
  { key: 'risk', label: '高风险账号数', value: stats.high_risk, help: '严重与高风险账号' },
  { key: 'change', label: '待强制改密账号数', value: stats.must_change, help: '已标记必须修改密码' },
  { key: 'safe', label: '符合当前策略账号数', value: stats.compliant, help: '密码安全状态正常' },
  { key: 'disabled', label: '已禁用账号数', value: stats.disabled, help: '当前处于暂停状态' }
])
const visiblePages = computed(() => {
  const start = Math.max(1, Math.min(pagination.page - 2, pagination.total_pages - 4))
  return Array.from({ length: Math.min(5, pagination.total_pages) }, (_, index) => start + index)
})
const regionOptions = computed(() => [...new Set(
  options.stations.map((item) => item.region).filter(Boolean)
)].sort((left, right) => left.localeCompare(right, 'zh-CN')))
const filteredStationOptions = computed(() => {
  if (!filters.station_region) return options.stations
  return options.stations.filter((item) => item.region === filters.station_region)
})
const appliedFilterChips = computed(() => {
  const role = options.roles.find((item) => item.value === appliedFilters.role)
  const station = options.stations.find((item) => String(item.id) === appliedFilters.station_id)
  const risk = options.risk_levels.find((item) => item.value === appliedFilters.risk_level)
  const chips = []
  if (appliedFilters.keyword) chips.push({ key: 'keyword', label: '搜索', value: appliedFilters.keyword })
  if (role) chips.push({ key: 'role', label: '角色', value: role.label })
  if (appliedFilters.station_region) chips.push({ key: 'station_region', label: '片区', value: appliedFilters.station_region })
  if (station) chips.push({ key: 'station_id', label: '站点', value: station.station_name })
  if (appliedFilters.risk_level) chips.push({
    key: 'risk_level',
    label: '风险',
    value: appliedFilters.risk_level === 'high_risk' ? '严重 + 高风险' : (risk?.label || appliedFilters.risk_level)
  })
  if (appliedFilters.must_change_password) chips.push({
    key: 'must_change_password',
    label: '改密',
    value: appliedFilters.must_change_password === 'true' ? '待强制改密' : '无需强制改密'
  })
  if (appliedFilters.account_status) chips.push({
    key: 'account_status',
    label: '状态',
    value: appliedFilters.account_status === 'active' ? '正常' : '已暂停'
  })
  if (appliedFilters.passkey_status) chips.push({
    key: 'passkey_status',
    label: 'Passkey',
    value: appliedFilters.passkey_status === 'bound' ? '已绑定' : '未绑定'
  })
  return chips
})

const showToast = (text, type = 'success') => {
  toast.text = text
  toast.type = type
  window.setTimeout(() => { if (toast.text === text) toast.text = '' }, 3000)
}
const accountParams = () => ({ ...appliedFilters, page: pagination.page, page_size: pagination.page_size })
const applyPolicy = (raw = {}) => {
  Object.assign(policy, raw)
  Object.assign(policyForm, {
    enforcement_mode: raw.enforcement_mode || 'observe', normal_min_length: Number(raw.normal_min_length || 12),
    privileged_min_length: Number(raw.privileged_min_length || 15), max_length: Number(raw.max_length || 64),
    require_uppercase: raw.require_uppercase !== false, require_lowercase: raw.require_lowercase !== false,
    require_number: raw.require_number !== false, require_special: raw.require_special !== false,
    history_count: Number(raw.history_count || 5), grace_period_days: Number(raw.grace_period_days || 30),
    logout_other_sessions: raw.logout_other_sessions !== false, forbid_identity_similarity: raw.forbid_identity_similarity !== false,
    weak_passwords_text: (raw.weak_passwords || []).join('\n')
  })
}
const loadAccounts = async (page = pagination.page) => {
  accountsLoading.value = true
  pagination.page = page
  try {
    const response = await axios.get('/api/management/security/accounts', { params: accountParams() })
    accounts.value = response.data.items || []
    Object.assign(stats, response.data.stats || {})
    Object.assign(options, response.data.options || {})
    Object.assign(pagination, { page: response.data.page, page_size: response.data.page_size, total: response.data.total, total_pages: response.data.total_pages })
    policy.enforcement_mode = response.data.policy_mode || policy.enforcement_mode
  } catch (error) { showToast(error?.response?.data?.error || '账号安全数据读取失败。', 'error') } finally { accountsLoading.value = false }
}
const loadPolicy = async () => {
  try { const response = await axios.get('/api/management/security/policy'); applyPolicy(response.data.policy || {}) }
  catch (error) { showToast(error?.response?.data?.error || '密码策略读取失败。', 'error') }
}
const loadLogs = async (page = logPagination.page) => {
  logsLoading.value = true
  try {
    const response = await axios.get('/api/management/security/logs', { params: { ...logFilters, page, page_size: logPagination.page_size } })
    logs.value = response.data.items || []
    Object.assign(logPagination, { page: response.data.page, page_size: response.data.page_size, total: response.data.total, total_pages: response.data.total_pages })
  } catch (error) { showToast(error?.response?.data?.error || '安全操作记录读取失败。', 'error') } finally { logsLoading.value = false }
}
const switchTab = (tab) => { activeTab.value = tab; if (tab === 'policy') loadPolicy(); if (tab === 'logs') loadLogs(1) }
const applyFilters = () => {
  Object.assign(appliedFilters, filters)
  loadAccounts(1)
}
const resetFilters = () => {
  Object.assign(filters, emptyAccountFilters())
  Object.assign(appliedFilters, emptyAccountFilters())
  loadAccounts(1)
}
const applyQuickFilter = (key, value) => {
  filters[key] = filters[key] === value ? '' : value
  applyFilters()
}
const handleRegionChange = () => {
  if (!filters.station_id) return
  const station = options.stations.find((item) => String(item.id) === filters.station_id)
  if (filters.station_region && station?.region !== filters.station_region) {
    filters.station_id = ''
  }
}
const removeAppliedFilter = (key) => {
  filters[key] = ''
  appliedFilters[key] = ''
  loadAccounts(1)
}
const closeDialog = () => { if (dialog.saving) return; Object.assign(dialog, { visible: false, type: '', title: '', description: '', account: null, requirePassword: false, currentPassword: '', affectedCount: null, highRiskCount: 0, suspendedCount: 0, roleCounts: {} }) }
const runAccountAction = async (account, action) => {
  const labels = { force_change: '强制下次登录改密', cancel_force_change: '取消强制改密', invalidate_sessions: '注销全部现有会话', suspend: '暂停账号', restore: '恢复账号' }
  if (!window.confirm(`确认对账号【${account.username}】执行“${labels[action]}”吗？`)) return
  try { const response = await axios.post(`/api/management/security/accounts/${account.id}/action`, { action }); showToast(response.data.message || '账号安全操作已完成。'); await loadAccounts() }
  catch (error) { showToast(error?.response?.data?.error || '账号安全操作失败。', 'error') }
}
const openImmediateDialog = (account) => Object.assign(dialog, { visible: true, type: 'immediate', title: '立即执行强制改密', description: `账号【${account.username}】的现有会话会立即失效，下次登录只能修改密码或退出。`, account, requirePassword: true, currentPassword: '', affectedCount: 1, highRiskCount: 1, saving: false })
const openInitializationDialog = async () => {
  try {
    const response = await axios.post('/api/management/security/password-initialization/preview')
    Object.assign(dialog, {
      visible: true,
      type: 'initialization',
      title: '所有用户一键初始化为强密码',
      description: '这是系统级高风险操作。确认后将为所有可处理账号生成独立强密码，并立即下载初始登录凭据。',
      requirePassword: true,
      currentPassword: '',
      affectedCount: response.data.affected_count,
      highRiskCount: 0,
      suspendedCount: response.data.suspended_count || 0,
      roleCounts: response.data.role_counts || {},
      saving: false
    })
  } catch (error) { showToast(error?.response?.data?.error || '初始化影响范围读取失败。', 'error') }
}
const readDownloadError = async (error) => {
  const payload = error?.response?.data
  if (!(payload instanceof Blob)) return payload?.error || '账号密码初始化失败。'
  try { return JSON.parse(await payload.text())?.error || '账号密码初始化失败。' }
  catch { return '账号密码初始化失败。' }
}
const downloadCredentialWorkbook = (response) => {
  const disposition = String(response.headers?.['content-disposition'] || '')
  const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  let filename = '用户初始登录凭据.xlsx'
  try { filename = decodeURIComponent(utf8Name || plainName || filename) } catch { filename = plainName || filename }
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const openPolicyConfirm = () => Object.assign(dialog, { visible: true, type: 'policy', title: policyForm.enforcement_mode !== policy.enforcement_mode ? '确认切换安全执行模式' : '确认保存密码策略', description: policyForm.enforcement_mode === 'enforce' ? '正式执行后，待强制改密账号将无法进入其他业务页面。' : '策略规则变化会生成新版本，并标记需要整改的账号。', requirePassword: true, currentPassword: '', affectedCount: null, highRiskCount: 0, saving: false })
const confirmDialog = async () => {
  dialog.saving = true
  try {
    let response
    if (dialog.type === 'immediate') response = await axios.post(`/api/management/security/accounts/${dialog.account.id}/action`, { action: 'force_change_immediately', current_password: dialog.currentPassword })
    if (dialog.type === 'initialization') {
      initialCredentialExporting.value = true
      try {
        response = await axios.post('/api/management/security/password-initialization/export', { current_password: dialog.currentPassword }, { responseType: 'blob', timeout: 120000 })
        downloadCredentialWorkbook(response)
      } catch (error) {
        throw new Error(await readDownloadError(error), { cause: error })
      } finally {
        initialCredentialExporting.value = false
      }
    }
    if (dialog.type === 'policy') {
      policySaving.value = true
      response = await axios.put('/api/management/security/policy', { ...policyForm, weak_passwords: policyForm.weak_passwords_text.split(/\r?\n/).map((item) => item.trim()).filter(Boolean), current_password: dialog.currentPassword })
      applyPolicy(response.data.policy || {})
    }
    showToast(response?.data?.message || '安全操作已完成。')
    dialog.saving = false
    closeDialog()
    await loadAccounts()
  } catch (error) { dialog.saving = false; showToast(error?.response?.data?.error || error?.message || '安全操作失败。', 'error') }
  finally { policySaving.value = false }
}
const viewAccountLogs = (account) => { logFilters.target_user_id = String(account.id); logFilters.keyword = ''; activeTab.value = 'logs'; loadLogs(1) }
const clearAccountLogFilter = () => { logFilters.target_user_id = ''; loadLogs(1) }
const actionLabel = (action) => ({ force_change: '强制下次登录改密', force_change_immediately: '立即执行强制改密', cancel_force_change: '取消强制改密', invalidate_sessions: '注销现有会话', suspend: '暂停账号', restore: '恢复账号', batch_force_change: '批量强制改密', batch_invalidate_sessions: '批量注销会话', bulk_password_initialization: '批量初始化账号密码', password_change: '用户修改密码', administrator_password_reset: '管理员重置密码', password_policy_update: '修改密码策略', plaintext_password_migration: '明文密码安全迁移', passkey_login: 'Passkey登录', root_passkey_bootstrap: 'root首次绑定Passkey', passkey_registration: '绑定Passkey', passkey_rename: '修改Passkey名称', passkey_delete: '删除Passkey', account_impersonation_start: 'Root代入账号', account_impersonation_end: 'Root退出代入' }[action] || action)

onMounted(async () => { await Promise.all([loadAccounts(1), loadPolicy()]) })
</script>

<style scoped>
.security-page,.security-page>*,.filter-grid,.filter-grid>label,.policy-grid>label,.section-heading>div{min-width:0}
.security-page{display:grid;gap:18px;color:#172033}.security-hero,.security-card,.stat-card{border:1px solid rgba(148,163,184,.22);border-radius:24px;background:rgba(255,255,255,.97);box-shadow:0 16px 42px rgba(15,23,42,.07)}.security-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:27px;background:radial-gradient(circle at 10% 20%,rgba(14,165,233,.16),transparent 34%),linear-gradient(135deg,#f8fbff,#f1fbf7)}.page-kicker,.section-heading>div>span{color:#087c71;font-size:12px;font-weight:900;letter-spacing:.14em}.security-hero h2{margin:7px 0;font-size:29px}.security-hero p,.section-heading p{margin:0;color:#657085}.mode-panel{min-width:230px;padding:15px 18px;border-radius:18px;display:grid;gap:4px;background:#fff7df;border:1px solid #f4d083}.mode-panel.enforce{background:#fff0ee;border-color:#f1a69f}.mode-panel span{font-size:12px;font-weight:900;color:#9a6810}.mode-panel.enforce span{color:#b23d36}.mode-panel strong{font-size:14px}.security-tabs{display:flex;gap:8px;padding:6px;border-radius:18px;background:#eaf0f5;width:max-content;max-width:100%;overflow-x:auto}.security-tabs button{border:0;background:transparent;border-radius:13px;padding:10px 16px;display:flex;align-items:center;gap:8px;color:#607085;white-space:nowrap}.security-tabs button span{display:grid;place-items:center;width:26px;height:26px;border-radius:9px;background:rgba(255,255,255,.8);font-weight:900}.security-tabs button.active{background:#fff;color:#0f766e;box-shadow:0 5px 15px rgba(15,23,42,.09)}.security-toast{position:fixed;z-index:1500;left:50%;top:86px;transform:translateX(-50%);padding:12px 22px;border-radius:14px;background:#0f766e;color:#fff;box-shadow:0 12px 35px rgba(15,23,42,.22);animation:toastIn .25s ease}.security-toast.error{background:#b93a38}.stats-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.stat-card{padding:18px;display:grid;gap:7px;position:relative;overflow:hidden}.stat-card:before{content:"";position:absolute;inset:0 auto 0 0;width:5px;background:#1d88bf}.stat-card.risk:before{background:#d24d45}.stat-card.change:before{background:#d49422}.stat-card.safe:before{background:#149169}.stat-card.disabled:before{background:#778293}.stat-card span{font-size:13px;color:#637084}.stat-card strong{font-size:28px}.stat-card small{color:#8a94a4}.security-card{padding:23px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:19px}.section-heading.compact{margin-bottom:15px}.section-heading h3{font-size:21px;margin:4px 0}.filter-actions,.section-heading .filter-actions{display:flex;gap:8px}.filter-grid{display:grid;grid-template-columns:1.5fr repeat(4,1fr);gap:12px}.filter-grid label,.policy-grid label,.confirm-dialog label{display:grid;gap:7px}.filter-grid label>span,.policy-grid label>span,.confirm-dialog label>span{font-size:12px;color:#536174;font-weight:800}.filter-grid input,.filter-grid select,.policy-grid input,.policy-grid textarea,.log-filters input,.log-filters select,.confirm-dialog input{width:100%;box-sizing:border-box;border:1px solid #d8e0e8;background:#fbfdff;border-radius:12px;padding:10px 12px;color:#172033;min-height:42px}.batch-button{background:#163e62;color:#fff;border-color:#163e62}.account-table-wrap{overflow-x:auto}.account-table{display:grid;grid-template-columns:36px minmax(140px,1.05fr) minmax(100px,.75fr) minmax(145px,1fr) minmax(200px,1.45fr) 90px 110px 86px minmax(170px,1.25fr);align-items:center;min-width:1160px}.account-table-head{padding:11px 13px;background:#eef4f8;border-radius:13px;color:#5b6879;font-size:12px;font-weight:900}.account-row{padding:13px;border-bottom:1px solid #e8edf2;transition:.2s}.account-row:hover{background:#f8fbfd}.account-row>div{padding:0 6px;display:grid;gap:4px}.account-row strong{font-size:13px}.account-row small{color:#7c8795;font-size:11px}.role-chip,.risk-chip,.status-chip,.boolean-chip,.result-chip{display:inline-flex;width:max-content;padding:5px 9px;border-radius:999px;font-size:11px;font-weight:900}.role-chip{background:#edf3f8;color:#31536e}.risk-chip.critical{background:#fde5e2;color:#b52e28}.risk-chip.high{background:#fff0df;color:#b55a16}.risk-chip.remediation{background:#fff7d8;color:#8f6a00}.risk-chip.normal{background:#e3f6ee;color:#087b57}.risk-chip.disabled,.status-chip.suspended{background:#e8ebef;color:#5d6570}.status-chip.active,.boolean-chip.active{background:#e3f6ee;color:#087b57}.boolean-chip{background:#eef2f5;color:#6b7480}.risk-reason{line-height:1.45}.date-text{font-size:12px;color:#586578}.account-actions{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}.account-actions button,.pagination-bar button{border:1px solid #cfd9e2;background:#fff;color:#31536e;border-radius:8px;padding:6px 7px;font-size:11px;white-space:nowrap}.account-actions .danger-outline{color:#b13b36;border-color:#efc0bc}.account-actions .restore{color:#087b57;border-color:#a9dfcb}.pagination-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:17px;color:#6e7988;font-size:12px}.pagination-bar>div{display:flex;gap:5px;flex-wrap:wrap}.pagination-bar button.active{background:#153f62;color:#fff;border-color:#153f62}.state-panel{min-height:180px;display:flex;align-items:center;justify-content:center;gap:12px;color:#536174}.state-panel.empty{flex-direction:column}.loading-ring{width:25px;height:25px;border:3px solid #d7e3ea;border-top-color:#0f766e;border-radius:50%;animation:spin .8s linear infinite}.policy-meta{display:grid;text-align:right;gap:3px}.policy-meta strong{font-size:24px}.policy-meta small{color:#778493}.mode-switch-card{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:18px;border-radius:17px;background:#f4f8fb;margin-bottom:17px}.mode-switch-card p{margin:4px 0 0;color:#687587;font-size:13px}.mode-options{display:flex;padding:4px;background:#e3eaf0;border-radius:12px}.mode-options button{border:0;background:transparent;padding:9px 15px;border-radius:9px}.mode-options button.active{background:#fff;color:#9a6810;box-shadow:0 4px 12px rgba(15,23,42,.1)}.mode-options button.enforce.active{color:#b13b36}.policy-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.policy-grid label small{color:#8490a0}.policy-grid .switch-field{grid-template-columns:1fr auto;align-items:center;padding:13px;border:1px solid #dde5eb;border-radius:14px}.policy-grid .switch-field input{width:22px;height:22px}.policy-grid .switch-field small{grid-column:1/-1}.weak-password-field{grid-column:span 2}.policy-grid textarea{resize:vertical}.policy-save-bar{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:18px;padding:15px 17px;border-radius:16px;background:#f7fafc}.policy-save-bar>div{display:grid;gap:3px}.policy-save-bar span{font-size:12px;color:#778493}.log-filters{display:grid;grid-template-columns:1fr 180px auto;gap:10px;margin-bottom:15px}.log-list{display:grid;gap:9px}.log-list article{display:grid;grid-template-columns:160px 1fr 145px;gap:16px;align-items:center;padding:14px;border:1px solid #e2e8ee;border-radius:15px}.log-time,.log-main,.log-source{display:grid;gap:5px}.log-time strong{font-size:12px}.result-chip.success{background:#e3f6ee;color:#087b57}.result-chip.failure{background:#fde5e2;color:#b52e28}.log-main span,.log-main small,.log-source{font-size:12px;color:#6b7788}.log-source{text-align:right}.modal-backdrop{position:fixed;inset:0;z-index:1400;background:rgba(15,23,42,.56);display:grid;place-items:center;padding:20px}.confirm-dialog{position:relative;width:min(500px,100%);background:#fff;border-radius:24px;padding:28px;box-shadow:0 28px 80px rgba(15,23,42,.3)}.modal-close{position:absolute;right:14px;top:14px;width:36px;height:36px;border-radius:50%;border:0;background:#fee5e3;color:#b52e28;font-size:24px}.dialog-mark{width:48px;height:48px;border-radius:16px;background:#e4f4f1;color:#0f766e;display:grid;place-items:center;font-weight:900}.confirm-dialog h3{margin:14px 0 7px}.confirm-dialog>p{color:#657085;line-height:1.6}.impact-panel{display:flex;align-items:baseline;gap:10px;padding:14px;border-radius:14px;background:#fff7e1;margin:15px 0}.impact-panel strong{font-size:28px;color:#a8620c}.impact-panel small{color:#956e36}.dialog-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:18px}.btn-danger{background:#b83b36;color:#fff;border-color:#b83b36}@keyframes spin{to{transform:rotate(360deg)}}@keyframes toastIn{from{opacity:0;transform:translate(-50%,-8px)}}
.account-batch-actions{display:flex;justify-content:flex-end;gap:9px;flex-wrap:wrap}.initialize-button{background:#9a3412;color:#fff;border-color:#9a3412}.initialization-scope{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.initialization-scope span{display:inline-flex;align-items:center;gap:5px;padding:6px 9px;border-radius:999px;background:#edf4f8;color:#526276;font-size:11px}.initialization-scope strong{color:#163e62}.initialization-warnings{display:grid;gap:7px;margin:12px 0 17px;padding:14px 14px 14px 32px;border:1px solid #f1c9a8;border-radius:14px;background:#fff8ef;color:#7c4722;font-size:12px;line-height:1.55}.credential-processing{position:fixed;inset:0;z-index:1700;display:grid;place-items:center;padding:20px;background:rgba(10,20,34,.78);backdrop-filter:blur(7px)}.credential-processing-card{width:min(480px,100%);box-sizing:border-box;padding:30px;border:1px solid rgba(255,255,255,.22);border-radius:26px;background:linear-gradient(155deg,#fff,#edf7f5);box-shadow:0 30px 90px rgba(0,0,0,.4);text-align:center}.processing-shield{width:66px;height:72px;margin:0 auto 16px;display:grid;place-items:center;clip-path:polygon(50% 0,94% 18%,85% 73%,50% 100%,15% 73%,6% 18%);background:linear-gradient(145deg,#0f766e,#163e62)}.processing-shield span{width:18px;height:18px;border:3px solid rgba(255,255,255,.42);border-top-color:#fff;border-radius:50%;animation:spin .75s linear infinite}.credential-processing-card h3{margin:0 0 8px;font-size:21px}.credential-processing-card p{margin:0;color:#5f6d7f;line-height:1.7}.credential-processing-card small{display:block;color:#7b8795;line-height:1.55}.processing-line{height:7px;margin:20px 0 13px;overflow:hidden;border-radius:999px;background:#dce8e8}.processing-line span{display:block;width:42%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#0f766e,#22a984,#1d88bf);animation:processingMove 1.2s ease-in-out infinite}@keyframes processingMove{0%{transform:translateX(-110%)}100%{transform:translateX(350%)}}
@media(max-width:1100px){.stats-grid{grid-template-columns:repeat(3,1fr)}.filter-grid{grid-template-columns:repeat(2,1fr)}.keyword-field{grid-column:span 2}.policy-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){.security-page{gap:13px}.security-hero{align-items:stretch;flex-direction:column;padding:20px;border-radius:20px}.security-hero h2{font-size:24px}.mode-panel{min-width:0}.security-tabs{width:100%;box-sizing:border-box}.security-tabs button{flex:1;justify-content:center;padding:9px}.security-tabs button span{display:none}.security-card{padding:16px;border-radius:19px}.stats-grid{grid-template-columns:repeat(2,1fr);gap:9px}.stat-card{padding:14px}.stat-card strong{font-size:24px}.stat-card.total{grid-column:span 2}.section-heading{align-items:flex-start;flex-direction:column}.section-heading .batch-button{width:100%}.filter-grid{grid-template-columns:1fr}.keyword-field{grid-column:auto}.filter-actions{width:100%}.filter-actions .btn{flex:1}.account-table-wrap{overflow:visible}.account-table-head{display:none}.account-table{min-width:0;display:block}.account-row{border:1px solid #e1e8ee;border-radius:17px;margin-bottom:10px;padding:13px}.account-row>div{display:flex;align-items:flex-start;justify-content:space-between;padding:7px 0;border-bottom:1px dashed #e7ecf0}.account-row>div:before{content:attr(data-label);color:#778393;font-size:12px;flex:0 0 82px}.account-row .select-cell{justify-content:flex-end}.account-row .select-cell:before{content:"选择账号"}.account-row>div>small,.account-row>div>.risk-reason{text-align:right;max-width:65%}.account-actions{display:grid!important;grid-template-columns:repeat(2,1fr)!important;border-bottom:0!important}.account-actions:before{display:none}.pagination-bar{align-items:stretch;flex-direction:column}.pagination-bar>div{display:grid;grid-template-columns:repeat(5,1fr)}.pagination-bar button{padding:8px 4px}.mode-switch-card,.policy-save-bar{align-items:stretch;flex-direction:column}.mode-options button{flex:1}.policy-grid{grid-template-columns:1fr}.weak-password-field{grid-column:auto}.policy-save-bar .btn{width:100%}.log-filters{grid-template-columns:1fr}.log-list article{grid-template-columns:1fr;gap:9px}.log-source{text-align:left;grid-template-columns:1fr 1fr}.confirm-dialog{padding:23px 18px}.impact-panel{flex-wrap:wrap}.security-toast{top:70px;width:calc(100% - 32px);box-sizing:border-box;text-align:center}}
@media(max-width:720px){.account-batch-actions{width:100%;display:grid}.account-batch-actions .btn{width:100%}.credential-processing-card{padding:24px 18px}.initialization-warnings{padding-left:28px}.confirm-dialog{max-height:calc(100dvh - 36px);overflow-y:auto}}

.account-search-row{display:grid;grid-template-columns:minmax(280px,1.35fr) minmax(320px,1fr);gap:16px;align-items:end;margin-bottom:15px;padding:16px;border:1px solid #dce7ec;border-radius:17px;background:linear-gradient(135deg,#f7fbfc,#f8fafc)}
.search-field{display:grid;gap:7px}.search-field>span,.quick-filter-group>span{font-size:12px;color:#536174;font-weight:800}
.search-control{display:grid;grid-template-columns:auto 1fr auto;align-items:center;min-height:46px;border:1px solid #cbd9e1;border-radius:14px;background:#fff;box-shadow:0 5px 14px rgba(15,23,42,.04)}
.search-control:focus-within{border-color:#128c80;box-shadow:0 0 0 3px rgba(18,140,128,.12)}
.search-control i{padding-left:13px;color:#0f766e;font-size:11px;font-style:normal;font-weight:900}
.search-control input{min-width:0;border:0;outline:0;background:transparent;padding:11px 10px;color:#172033;font-size:14px}
.search-control button{width:34px;height:34px;margin-right:5px;border:0;border-radius:10px;background:#edf3f6;color:#667586;font-size:20px;line-height:1}
.quick-filter-group{display:grid;gap:7px}.quick-filter-group>div{display:flex;gap:7px;flex-wrap:wrap}
.quick-filter-group button{min-height:39px;padding:8px 12px;border:1px solid #d2dde4;border-radius:12px;background:#fff;color:#58677a;font-weight:800}
.quick-filter-group button.active{border-color:#0f766e;background:#e3f5f1;color:#08756a;box-shadow:inset 0 0 0 1px rgba(15,118,110,.08)}
.filter-card .filter-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.applied-filter-strip{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:15px;padding-top:14px;border-top:1px dashed #d8e2e8}
.applied-filter-title{color:#7a8797;font-size:11px;font-weight:900}
.applied-filter-strip button{display:inline-flex;align-items:center;gap:5px;max-width:240px;padding:6px 8px;border:1px solid #cbe0dc;border-radius:10px;background:#eff8f6;color:#315e5a}
.applied-filter-strip button small{color:#6c7d7b}.applied-filter-strip button strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}.applied-filter-strip button b{color:#a34640;font-size:14px}
.applied-filter-count{margin-left:auto;color:#607083;font-size:12px;font-weight:800}

@media(max-width:1100px){.account-search-row{grid-template-columns:1fr}.account-search-row .keyword-field{grid-column:auto}.filter-card .filter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:720px){.account-search-row{padding:13px;gap:13px}.quick-filter-group>div{display:grid;grid-template-columns:1fr}.filter-card .filter-grid{grid-template-columns:1fr}.applied-filter-strip{align-items:stretch}.applied-filter-strip button{max-width:100%;justify-content:flex-start}.applied-filter-count{width:100%;margin-left:0;padding-top:3px}}

@media(min-width:721px){
  .account-table{grid-template-columns:minmax(140px,1.05fr) minmax(100px,.75fr) minmax(145px,1fr) minmax(200px,1.45fr) minmax(110px,.8fr) 90px 110px 86px minmax(170px,1.25fr);min-width:1240px}
}
.login-method-chip{display:inline-flex;width:max-content;padding:5px 9px;border-radius:999px;background:#eef2f5;color:#617080;font-size:11px;font-weight:900}
.login-method-chip.passkey{background:#e1f5f1;color:#08766c}
</style>
