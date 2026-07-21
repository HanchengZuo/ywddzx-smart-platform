<template>
  <div class="page-shell auto-audit-page">
    <header class="page-header card-surface">
      <div>
        <div class="page-kicker">管理系统</div>
        <h2>白名单自动审核管理</h2>
        <p>用外部规范ID或问题描述关键词建立规则，帮助审核人员自动处理明确、重复的问题。</p>
      </div>
      <button class="btn btn-primary create-rule-btn" type="button" @click="openCreateDialog">
        <span>+</span>新增自动审核规则
      </button>
    </header>

    <transition name="toast-fade">
      <div v-if="notice.text" class="action-toast card-surface" :class="notice.type">{{ notice.text }}</div>
    </transition>

    <section class="overview-grid">
      <article class="workflow-card card-surface">
        <div class="workflow-copy">
          <div class="section-kicker">执行时机</div>
          <h3>完成确认后，再自动审核</h3>
          <p>只有当巡检记录的所有检查人确认完成，或系统到期自动确认完成后，才会执行下方规则。已经人工审核的问题不会被覆盖。</p>
        </div>
        <div class="workflow-steps" aria-label="自动审核流程">
          <div><strong>1</strong><span>检查人全部确认</span></div>
          <i></i>
          <div><strong>2</strong><span>按优先级匹配规则</span></div>
          <i></i>
          <div><strong>3</strong><span>自动通过或否决</span></div>
        </div>
        <div class="workflow-note">优先级数字越小越先执行；同一问题只使用第一条命中规则。</div>
      </article>

      <div class="metric-grid">
        <article class="metric-card card-surface rules">
          <span>规则</span>
          <strong>{{ summary.rule_enabled }}<em>/{{ summary.rule_total }}</em></strong>
          <small>启用 / 全部</small>
        </article>
        <article class="metric-card card-surface approved">
          <span>自动通过</span>
          <strong>{{ summary.approved }}</strong>
          <small>累计问题</small>
        </article>
        <article class="metric-card card-surface rejected">
          <span>自动否决</span>
          <strong>{{ summary.rejected }}</strong>
          <small>累计问题</small>
        </article>
        <article class="metric-card card-surface today">
          <span>今日执行</span>
          <strong>{{ summary.today }}</strong>
          <small>已自动审核</small>
        </article>
      </div>
    </section>

    <section class="rules-card card-surface">
      <div class="section-head">
        <div>
          <div class="section-kicker">规则中心</div>
          <h3>自动审核规则</h3>
          <p>相同触发条件只能建立一条规则，需要改变结论时请直接编辑。</p>
        </div>
        <button class="btn btn-secondary" type="button" :disabled="loading" @click="fetchData">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
      </div>

      <div v-if="loading && !rules.length" class="empty-state">正在加载自动审核规则...</div>
      <div v-else-if="!rules.length" class="empty-state rich">
        <strong>还没有自动审核规则</strong>
        <span>可以先从结论明确的外部规范ID开始配置。</span>
        <button class="btn btn-primary btn-sm" type="button" @click="openCreateDialog">新增第一条规则</button>
      </div>
      <div v-else class="rule-list">
        <article v-for="rule in rules" :key="rule.id" class="rule-row" :class="{ disabled: !rule.is_enabled }">
          <div class="priority-block">
            <span>优先级</span>
            <strong>{{ rule.priority }}</strong>
          </div>
          <div class="rule-main">
            <div class="rule-title-line">
              <h4>{{ rule.rule_name }}</h4>
              <span :class="['decision-chip', rule.decision]">{{ decisionLabel(rule.decision) }}</span>
              <span :class="['enabled-chip', rule.is_enabled ? 'enabled' : 'disabled']">
                {{ rule.is_enabled ? '执行中' : '已停用' }}
              </span>
            </div>
            <div class="condition-line">
              <span>{{ matchTypeLabel(rule.match_type) }}</span>
              <strong>{{ rule.match_value }}</strong>
            </div>
            <p v-if="rule.remark">{{ rule.remark }}</p>
            <div class="rule-meta">
              <span>已命中 {{ rule.matched_count || 0 }} 条</span>
              <span>最后命中 {{ rule.last_triggered_at || '暂无' }}</span>
              <span>更新人 {{ rule.updated_by_name || '-' }}</span>
              <span>{{ rule.updated_at || '-' }}</span>
            </div>
          </div>
          <div class="rule-actions">
            <label class="rule-switch" :title="rule.is_enabled ? '点击停用' : '点击启用'">
              <input :checked="rule.is_enabled" type="checkbox" :disabled="actingRuleId === rule.id"
                @change="toggleRule(rule, $event.target.checked)" />
              <span></span>
            </label>
            <button class="btn btn-secondary btn-sm" type="button" @click="openEditDialog(rule)">编辑</button>
            <button class="btn btn-danger btn-sm" type="button" :disabled="actingRuleId === rule.id"
              @click="deleteRule(rule)">删除</button>
          </div>
        </article>
      </div>
    </section>

    <section class="history-card card-surface">
      <div class="section-head history-head">
        <div>
          <div class="section-kicker">回溯记录</div>
          <h3>已自动审核的问题</h3>
          <p>记录保留触发当时的规则和问题快照，规则修改或删除后仍可查看。</p>
        </div>
        <div class="history-total">共 <strong>{{ history.total }}</strong> 条</div>
      </div>

      <div class="history-filters">
        <label>
          <span>审核结论</span>
          <select v-model="filters.decision" @change="applyFilters">
            <option value="">全部结论</option>
            <option value="approved">自动通过</option>
            <option value="rejected">自动否决</option>
          </select>
        </label>
        <label>
          <span>命中规则</span>
          <select v-model="filters.rule_id" @change="applyFilters">
            <option value="">全部规则</option>
            <option v-for="rule in rules" :key="`filter-${rule.id}`" :value="String(rule.id)">{{ rule.rule_name }}</option>
          </select>
        </label>
        <label class="keyword-filter">
          <span>搜索问题</span>
          <div>
            <input v-model.trim="filters.keyword" type="search" placeholder="问题ID、外部规范ID、站点或问题描述"
              @keyup.enter="applyFilters" />
            <button class="btn btn-primary btn-sm" type="button" @click="applyFilters">查询</button>
          </div>
        </label>
        <button class="btn btn-secondary reset-filter-btn" type="button" @click="resetFilters">重置筛选</button>
      </div>

      <div class="history-table-wrap">
        <table class="history-table">
          <thead>
            <tr>
              <th>执行时间</th>
              <th>问题</th>
              <th>站点 / 检查表</th>
              <th>外部规范ID</th>
              <th>问题描述</th>
              <th>命中规则</th>
              <th>结论</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="historyLoading">
              <td colspan="7" class="empty-cell">正在加载自动审核记录...</td>
            </tr>
            <tr v-else-if="!history.items.length">
              <td colspan="7" class="empty-cell">当前没有符合条件的自动审核记录。</td>
            </tr>
            <tr v-for="item in history.items" :key="item.id">
              <td class="nowrap">{{ item.triggered_at }}</td>
              <td>
                <strong>#{{ item.issue_reference_id }}</strong>
                <small v-if="!item.issue_id">原问题已删除</small>
              </td>
              <td>
                <strong>{{ item.station_name || '-' }}</strong>
                <small>{{ item.inspection_table_name || '-' }}</small>
              </td>
              <td><span class="standard-chip">{{ item.external_standard_id || '-' }}</span></td>
              <td class="description-cell">{{ item.issue_description || '-' }}</td>
              <td>
                <strong>{{ item.rule_name }}</strong>
                <small>{{ matchTypeLabel(item.match_type) }}：{{ item.match_value }}</small>
              </td>
              <td><span :class="['decision-chip', item.decision]">{{ decisionLabel(item.decision) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="history.total" class="pagination-bar">
        <div class="pagination-summary">第 {{ history.page }} / {{ history.total_pages }} 页</div>
        <div class="pagination-controls">
          <button class="btn btn-secondary pagination-btn" type="button" :disabled="history.page <= 1"
            @click="goToPage(1)">首页</button>
          <button class="btn btn-secondary pagination-btn" type="button" :disabled="history.page <= 1"
            @click="goToPage(history.page - 1)">上一页</button>
          <div class="pagination-page-list">
            <template v-for="item in visiblePageItems" :key="item.key">
              <span v-if="item.type === 'ellipsis'" class="pagination-ellipsis">...</span>
              <button v-else class="pagination-page-btn" :class="{ active: item.value === history.page }" type="button"
                @click="goToPage(item.value)">{{ item.value }}</button>
            </template>
          </div>
          <button class="btn btn-secondary pagination-btn" type="button" :disabled="history.page >= history.total_pages"
            @click="goToPage(history.page + 1)">下一页</button>
          <button class="btn btn-secondary pagination-btn" type="button" :disabled="history.page >= history.total_pages"
            @click="goToPage(history.total_pages)">末页</button>
        </div>
      </div>
    </section>

    <div v-if="dialog.visible" class="modal-backdrop">
      <section class="rule-modal mobile-detail-sheet card-surface" role="dialog" aria-modal="true"
        :aria-label="dialogTitle">
        <button class="modal-close" type="button" :disabled="dialog.saving" @click="closeDialog">×</button>
        <div class="modal-head">
          <div class="section-kicker">{{ dialog.mode === 'create' ? '新建规则' : '编辑规则' }}</div>
          <h3>{{ dialogTitle }}</h3>
          <p>规则只在巡检记录确认完成时执行，不会追溯修改已审核的历史问题。</p>
        </div>

        <div v-if="dialog.error" class="form-error">{{ dialog.error }}</div>

        <form class="rule-form" @submit.prevent="saveRule">
          <label class="field-wide">
            <span>规则名称</span>
            <input v-model.trim="dialog.form.rule_name" maxlength="80" placeholder="例如：收银台规范自动通过" />
          </label>

          <label>
            <span>触发指标</span>
            <select v-model="dialog.form.match_type" @change="dialog.form.match_value = ''">
              <option value="external_standard_id">外部规范ID</option>
              <option value="description_keyword">问题描述关键词</option>
            </select>
            <small>{{ matchTypeHelp(dialog.form.match_type) }}</small>
          </label>

          <label>
            <span>{{ dialog.form.match_type === 'external_standard_id' ? '完整外部规范ID' : '连续关键词' }}</span>
            <input v-model.trim="dialog.form.match_value"
              :type="dialog.form.match_type === 'external_standard_id' ? 'number' : 'text'"
              :placeholder="dialog.form.match_type === 'external_standard_id' ? '例如：1000' : '例如：未张贴公示牌'" />
            <small>{{ dialog.form.match_type === 'external_standard_id' ? '只有ID完全相等才会命中。' : '不区分英文大小写，需至少2个字符。' }}</small>
          </label>

          <fieldset class="decision-field field-wide">
            <legend>自动审核结论</legend>
            <label :class="{ selected: dialog.form.decision === 'approved' }">
              <input v-model="dialog.form.decision" type="radio" value="approved" />
              <strong>自动通过</strong>
              <small>问题继续进入站经理签字与整改流程。</small>
            </label>
            <label class="reject" :class="{ selected: dialog.form.decision === 'rejected' }">
              <input v-model="dialog.form.decision" type="radio" value="rejected" />
              <strong>自动否决</strong>
              <small>问题不再参与巡检记录统计和后续流转。</small>
            </label>
          </fieldset>

          <label>
            <span>执行优先级</span>
            <input v-model.number="dialog.form.priority" type="number" min="1" max="9999" />
            <small>数字越小越先执行，建议按 10、20、30 留出调整空间。</small>
          </label>

          <label class="enabled-field">
            <span>规则状态</span>
            <div class="enabled-control">
              <input v-model="dialog.form.is_enabled" type="checkbox" />
              <strong>{{ dialog.form.is_enabled ? '保存后立即启用' : '保存为停用状态' }}</strong>
            </div>
            <small>停用规则不会删除已有命中记录。</small>
          </label>

          <label class="field-wide">
            <span>备注（可选）</span>
            <textarea v-model.trim="dialog.form.remark" rows="3" maxlength="500"
              placeholder="记录设置该规则的业务原因，方便后续维护。"></textarea>
          </label>

          <div class="modal-actions field-wide">
            <button class="btn btn-secondary" type="button" :disabled="dialog.saving" @click="closeDialog">取消</button>
            <button class="btn btn-primary" type="submit" :disabled="dialog.saving">
              {{ dialog.saving ? '保存中...' : (dialog.mode === 'create' ? '创建规则' : '保存修改') }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import axios from 'axios'

const loading = ref(false)
const historyLoading = ref(false)
const rules = ref([])
const actingRuleId = ref(null)
const summary = reactive({
  rule_total: 0,
  rule_enabled: 0,
  approved: 0,
  rejected: 0,
  today: 0,
  total: 0
})
const history = reactive({
  items: [],
  page: 1,
  page_size: 20,
  total: 0,
  total_pages: 1
})
const filters = reactive({ decision: '', rule_id: '', keyword: '' })
const notice = reactive({ text: '', type: 'success', timer: null })

const createEmptyRuleForm = () => ({
  rule_name: '',
  match_type: 'external_standard_id',
  match_value: '',
  decision: 'approved',
  priority: 100,
  is_enabled: true,
  remark: ''
})

const dialog = reactive({
  visible: false,
  mode: 'create',
  ruleId: null,
  form: createEmptyRuleForm(),
  saving: false,
  error: ''
})

const dialogTitle = computed(() => dialog.mode === 'create' ? '新增自动审核规则' : '编辑自动审核规则')

const visiblePageItems = computed(() => {
  const total = history.total_pages
  const current = history.page
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => ({ type: 'page', value: index + 1, key: `page-${index + 1}` }))
  }
  const pages = new Set([1, total, current - 1, current, current + 1])
  const values = [...pages].filter((value) => value >= 1 && value <= total).sort((a, b) => a - b)
  const result = []
  values.forEach((value, index) => {
    if (index > 0 && value - values[index - 1] > 1) {
      result.push({ type: 'ellipsis', key: `ellipsis-${values[index - 1]}-${value}` })
    }
    result.push({ type: 'page', value, key: `page-${value}` })
  })
  return result
})

const showNotice = (text, type = 'success') => {
  if (notice.timer) window.clearTimeout(notice.timer)
  notice.text = text
  notice.type = type
  notice.timer = window.setTimeout(() => {
    notice.text = ''
    notice.timer = null
  }, 3200)
}

const matchTypeLabel = (value) => value === 'external_standard_id' ? '外部规范ID' : '问题描述关键词'
const matchTypeHelp = (value) => value === 'external_standard_id'
  ? '适合针对某一条明确的外部规范建立固定结论。'
  : '问题描述中出现连续关键词时命中，配置前请避免使用过于宽泛的词。'
const decisionLabel = (value) => value === 'rejected' ? '自动否决' : '自动通过'

const applyResponse = (data = {}) => {
  rules.value = Array.isArray(data.rules) ? data.rules : []
  Object.assign(summary, data.summary || {})
  Object.assign(history, data.history || { items: [], page: 1, page_size: 20, total: 0, total_pages: 1 })
}

const fetchData = async ({ page = history.page, silent = false } = {}) => {
  if (!silent) loading.value = true
  historyLoading.value = true
  try {
    const response = await axios.get('/api/management/auto-audit', {
      params: {
        user_id: localStorage.getItem('user_id') || '',
        page,
        page_size: history.page_size,
        decision: filters.decision,
        rule_id: filters.rule_id,
        keyword: filters.keyword
      }
    })
    applyResponse(response.data)
  } catch (error) {
    showNotice(error?.response?.data?.error || '加载自动审核管理数据失败。', 'error')
  } finally {
    loading.value = false
    historyLoading.value = false
  }
}

const applyFilters = () => fetchData({ page: 1 })
const resetFilters = () => {
  filters.decision = ''
  filters.rule_id = ''
  filters.keyword = ''
  fetchData({ page: 1 })
}
const goToPage = (page) => {
  const target = Math.min(history.total_pages, Math.max(1, Number(page) || 1))
  if (target === history.page) return
  fetchData({ page: target, silent: true })
}

const openCreateDialog = () => {
  dialog.mode = 'create'
  dialog.ruleId = null
  dialog.form = createEmptyRuleForm()
  dialog.error = ''
  dialog.visible = true
}

const openEditDialog = (rule) => {
  dialog.mode = 'edit'
  dialog.ruleId = rule.id
  dialog.form = {
    rule_name: rule.rule_name || '',
    match_type: rule.match_type || 'external_standard_id',
    match_value: String(rule.match_value || ''),
    decision: rule.decision || 'approved',
    priority: Number(rule.priority) || 100,
    is_enabled: Boolean(rule.is_enabled),
    remark: rule.remark || ''
  }
  dialog.error = ''
  dialog.visible = true
}

const closeDialog = () => {
  if (dialog.saving) return
  dialog.visible = false
  dialog.error = ''
}

const buildRulePayload = (form) => ({
  user_id: localStorage.getItem('user_id') || '',
  rule_name: form.rule_name,
  match_type: form.match_type,
  match_value: String(form.match_value || '').trim(),
  decision: form.decision,
  priority: Number(form.priority),
  is_enabled: Boolean(form.is_enabled),
  remark: form.remark
})

const saveRule = async () => {
  dialog.saving = true
  dialog.error = ''
  try {
    const payload = buildRulePayload(dialog.form)
    const response = dialog.mode === 'create'
      ? await axios.post('/api/management/auto-audit/rules', payload)
      : await axios.put(`/api/management/auto-audit/rules/${dialog.ruleId}`, payload)
    dialog.visible = false
    dialog.error = ''
    await fetchData({ page: 1, silent: true })
    showNotice(response.data?.message || '自动审核规则已保存。')
  } catch (error) {
    dialog.error = error?.response?.data?.error || '保存自动审核规则失败。'
  } finally {
    dialog.saving = false
  }
}

const toggleRule = async (rule, enabled) => {
  actingRuleId.value = rule.id
  try {
    const response = await axios.put(`/api/management/auto-audit/rules/${rule.id}`, {
      ...buildRulePayload(rule),
      is_enabled: enabled
    })
    rule.is_enabled = enabled
    summary.rule_enabled = rules.value.filter((item) => item.is_enabled).length
    showNotice(response.data?.message || (enabled ? '规则已启用。' : '规则已停用。'))
  } catch (error) {
    showNotice(error?.response?.data?.error || '修改规则状态失败。', 'error')
  } finally {
    actingRuleId.value = null
  }
}

const deleteRule = async (rule) => {
  if (!window.confirm(`确认删除规则“${rule.rule_name}”吗？\n已产生的自动审核回溯记录会继续保留。`)) return
  actingRuleId.value = rule.id
  try {
    const response = await axios.delete(`/api/management/auto-audit/rules/${rule.id}`, {
      data: { user_id: localStorage.getItem('user_id') || '' }
    })
    filters.rule_id = filters.rule_id === String(rule.id) ? '' : filters.rule_id
    await fetchData({ page: 1, silent: true })
    showNotice(response.data?.message || '规则已删除。')
  } catch (error) {
    showNotice(error?.response?.data?.error || '删除自动审核规则失败。', 'error')
  } finally {
    actingRuleId.value = null
  }
}

onMounted(() => fetchData({ page: 1 }))

onBeforeUnmount(() => {
  if (notice.timer) window.clearTimeout(notice.timer)
})
</script>

<style scoped>
.auto-audit-page {
  --audit-blue: #125b8c;
  --audit-cyan: #0f7b82;
  --audit-ink: #17324a;
  --audit-line: #d9e5ec;
  --audit-soft: #eef6f8;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 22px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  color: var(--audit-ink);
}

.auto-audit-page > *,
.overview-grid > *,
.page-header > * {
  min-width: 0;
}

.card-surface {
  border: 1px solid rgba(160, 185, 199, 0.5);
  box-shadow: 0 14px 34px rgba(26, 64, 85, 0.08);
}

.page-header {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 30px;
  background:
    linear-gradient(110deg, rgba(255, 255, 255, 0.98), rgba(235, 247, 248, 0.96)),
    repeating-linear-gradient(90deg, transparent 0 30px, rgba(18, 91, 140, 0.04) 30px 31px);
}

.page-header::after {
  content: '';
  position: absolute;
  inset: auto -70px -100px auto;
  width: 240px;
  height: 240px;
  border: 42px solid rgba(15, 123, 130, 0.08);
  border-radius: 50%;
}

.page-header > * { position: relative; z-index: 1; }
.page-kicker,
.section-kicker { color: var(--audit-cyan); font-size: 12px; font-weight: 800; letter-spacing: 0.14em; }
.page-header h2 { margin: 7px 0 8px; font-size: clamp(25px, 3vw, 34px); letter-spacing: -0.03em; }
.page-header p,
.section-head p,
.modal-head p { margin: 0; color: #648093; line-height: 1.75; }
.create-rule-btn { min-width: 190px; }
.create-rule-btn span { margin-right: 7px; font-size: 19px; }

.action-toast {
  position: fixed;
  z-index: 3500;
  top: 88px;
  left: 50%;
  transform: translateX(-50%);
  min-width: min(420px, calc(100vw - 32px));
  padding: 14px 20px;
  text-align: center;
  font-weight: 750;
  border-color: #8ac8ac;
  background: #effbf4;
  color: #147045;
}
.action-toast.error { border-color: #efb2b0; background: #fff2f1; color: #a83531; }

.overview-grid { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(380px, 1fr); gap: 18px; }
.workflow-card { padding: 24px; background: linear-gradient(135deg, #103f60 0%, #126c78 100%); color: #fff; }
.workflow-card .section-kicker { color: #8ee7db; }
.workflow-card h3 { margin: 8px 0 9px; font-size: 22px; }
.workflow-card p { margin: 0; color: rgba(255, 255, 255, 0.76); line-height: 1.7; }
.workflow-steps { display: flex; align-items: center; margin: 24px 0 17px; }
.workflow-steps div { flex: 1; display: grid; justify-items: center; gap: 8px; text-align: center; font-size: 13px; font-weight: 700; }
.workflow-steps strong { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: #fff; color: #115b73; }
.workflow-steps i { width: 46px; height: 1px; background: rgba(255, 255, 255, 0.35); }
.workflow-note { padding: 10px 13px; border: 1px solid rgba(255, 255, 255, 0.17); border-radius: 10px; background: rgba(255, 255, 255, 0.08); color: #dff7f3; font-size: 13px; }

.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.metric-card { position: relative; overflow: hidden; padding: 19px; background: #fff; }
.metric-card::before { content: ''; position: absolute; inset: 0 auto 0 0; width: 4px; background: #5a87a2; }
.metric-card.approved::before { background: #26a36d; }
.metric-card.rejected::before { background: #d95c54; }
.metric-card.today::before { background: #d79226; }
.metric-card span { display: block; color: #668093; font-size: 13px; font-weight: 700; }
.metric-card strong { display: block; margin: 6px 0 2px; font-size: 28px; letter-spacing: -0.04em; }
.metric-card strong em { color: #91a5b1; font-size: 15px; font-style: normal; font-weight: 700; }
.metric-card small { color: #92a5b0; }

.rules-card,
.history-card { padding: 25px; background: rgba(255, 255, 255, 0.97); }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.section-head h3 { margin: 6px 0 5px; font-size: 22px; }
.section-head p { font-size: 13px; }
.empty-state { padding: 48px 20px; text-align: center; color: #718897; background: #f6fafb; border: 1px dashed #cadce5; border-radius: 14px; }
.empty-state.rich { display: grid; justify-items: center; gap: 9px; }
.empty-state.rich strong { color: #29485d; font-size: 18px; }

.rule-list { display: grid; gap: 11px; }
.rule-row { display: grid; grid-template-columns: 82px minmax(0, 1fr) auto; align-items: stretch; min-height: 132px; border: 1px solid var(--audit-line); border-radius: 15px; overflow: hidden; transition: 0.2s ease; }
.rule-row:hover { border-color: #9fc5d2; box-shadow: 0 10px 24px rgba(32, 80, 102, 0.09); transform: translateY(-1px); }
.rule-row.disabled { opacity: 0.68; background: #f8fafb; }
.priority-block { display: grid; place-content: center; text-align: center; background: #eff6f8; border-right: 1px solid var(--audit-line); }
.priority-block span { color: #76909e; font-size: 11px; font-weight: 800; }
.priority-block strong { margin-top: 3px; font-size: 25px; color: var(--audit-blue); }
.rule-main { min-width: 0; padding: 17px 19px; }
.rule-title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.rule-title-line h4 { margin: 0 4px 0 0; font-size: 17px; }
.decision-chip,
.enabled-chip { display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; font-size: 12px; font-weight: 800; white-space: nowrap; }
.decision-chip { padding: 5px 9px; }
.decision-chip.approved { color: #13724c; background: #e5f7ed; border: 1px solid #b7e5ca; }
.decision-chip.rejected { color: #aa3c37; background: #fff0ef; border: 1px solid #f1c0bd; }
.enabled-chip { padding: 4px 8px; color: #257c68; background: #e9f7f3; }
.enabled-chip.disabled { color: #778b96; background: #edf1f3; }
.condition-line { display: flex; align-items: center; gap: 10px; margin: 12px 0 7px; }
.condition-line span { color: #6d8493; font-size: 12px; font-weight: 700; }
.condition-line strong,
.standard-chip { padding: 5px 9px; border-radius: 7px; background: #edf5f8; color: #155b7e; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.rule-main > p { margin: 8px 0; color: #627b8b; font-size: 13px; }
.rule-meta { display: flex; flex-wrap: wrap; gap: 7px 16px; margin-top: 11px; color: #879aa5; font-size: 11px; }
.rule-actions { display: flex; align-items: center; gap: 8px; padding: 16px; border-left: 1px solid #e5edf1; }
.rule-switch input { position: absolute; opacity: 0; }
.rule-switch span { position: relative; display: block; width: 42px; height: 23px; border-radius: 999px; background: #bcc9d0; cursor: pointer; transition: 0.2s; }
.rule-switch span::after { content: ''; position: absolute; top: 3px; left: 3px; width: 17px; height: 17px; border-radius: 50%; background: white; box-shadow: 0 2px 5px rgba(0,0,0,.16); transition: 0.2s; }
.rule-switch input:checked + span { background: #1b9b78; }
.rule-switch input:checked + span::after { transform: translateX(19px); }

.history-head { align-items: center; }
.history-total { flex: none; padding: 10px 14px; border-radius: 10px; background: var(--audit-soft); color: #69818f; }
.history-total strong { color: var(--audit-blue); font-size: 19px; }
.history-filters { display: grid; grid-template-columns: 180px 220px minmax(280px, 1fr) auto; align-items: end; gap: 12px; padding: 15px; margin-bottom: 18px; border-radius: 13px; background: #f3f8fa; }
.history-filters label { display: grid; gap: 6px; }
.history-filters label > span { color: #657f90; font-size: 12px; font-weight: 800; }
.history-filters select,
.history-filters input,
.rule-form input,
.rule-form select,
.rule-form textarea { width: 100%; border: 1px solid #c9d9e1; border-radius: 9px; background: #fff; color: #253f51; outline: none; transition: 0.18s; box-sizing: border-box; }
.history-filters select,
.history-filters input { height: 39px; padding: 0 11px; }
.history-filters select:focus,
.history-filters input:focus,
.rule-form input:focus,
.rule-form select:focus,
.rule-form textarea:focus { border-color: #4b9bab; box-shadow: 0 0 0 3px rgba(75, 155, 171, 0.12); }
.keyword-filter > div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 7px; }
.reset-filter-btn { height: 39px; }
.history-table-wrap { width: 100%; max-width: 100%; overflow-x: auto; border: 1px solid var(--audit-line); border-radius: 13px; box-sizing: border-box; }
.history-table { width: 100%; min-width: 1080px; border-collapse: collapse; }
.history-table th { padding: 12px 11px; background: #edf5f7; color: #567184; font-size: 12px; text-align: left; white-space: nowrap; }
.history-table td { padding: 13px 11px; border-top: 1px solid #e6eef2; vertical-align: middle; font-size: 13px; }
.history-table td strong { display: block; color: #28495f; }
.history-table td small { display: block; margin-top: 4px; color: #8498a5; line-height: 1.45; }
.description-cell { min-width: 230px; max-width: 360px; line-height: 1.55; }
.nowrap { white-space: nowrap; }
.empty-cell { padding: 42px !important; text-align: center !important; color: #7b909d; }

.pagination-bar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-top: 17px; }
.pagination-summary { color: #6f8795; font-size: 13px; }
.pagination-controls { display: flex; align-items: center; gap: 7px; }
.pagination-page-list { display: flex; gap: 5px; }
.pagination-page-btn { min-width: 34px; height: 34px; padding: 0 8px; border: 1px solid #cadbe3; border-radius: 8px; background: #fff; color: #49677a; cursor: pointer; }
.pagination-page-btn.active { border-color: var(--audit-blue); background: var(--audit-blue); color: #fff; }
.pagination-ellipsis { padding: 6px 2px; color: #8ba0ac; }

.modal-backdrop { position: fixed; z-index: 3000; inset: 0; display: grid; place-items: center; padding: 28px; background: rgba(15, 35, 49, 0.62); backdrop-filter: blur(6px); }
.rule-modal { position: relative; width: min(880px, calc(100vw - 40px)); max-height: calc(100vh - 50px); overflow-y: auto; padding: 28px; border-radius: 19px; background: #fff; }
.modal-close { position: sticky; z-index: 4; float: right; top: 0; display: grid; place-items: center; width: 42px; height: 42px; margin: -12px -12px 0 15px; border: 1px solid rgba(209, 80, 74, 0.35); border-radius: 50%; background: rgba(255, 241, 240, 0.95); color: #c83934; font-size: 27px; line-height: 1; cursor: pointer; }
.modal-head { padding: 3px 54px 19px 0; border-bottom: 1px solid #e3ecef; }
.modal-head h3 { margin: 7px 0 7px; font-size: 23px; }
.form-error { margin-top: 15px; padding: 11px 13px; border: 1px solid #efc0bd; border-radius: 9px; background: #fff3f2; color: #a83a35; font-weight: 700; }
.rule-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; padding-top: 20px; }
.rule-form > label { display: grid; align-content: start; gap: 7px; }
.rule-form > label > span,
.decision-field legend { color: #3b596c; font-size: 13px; font-weight: 800; }
.rule-form input,
.rule-form select { height: 43px; padding: 0 12px; }
.rule-form textarea { min-height: 88px; padding: 11px 12px; resize: vertical; }
.rule-form small { color: #8094a0; line-height: 1.45; }
.field-wide { grid-column: 1 / -1; }
.decision-field { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px; margin: 0; padding: 0; border: 0; }
.decision-field legend { margin-bottom: 8px; }
.decision-field label { position: relative; display: grid; gap: 4px; padding: 15px 15px 15px 43px; border: 1px solid #cfe0e5; border-radius: 12px; cursor: pointer; }
.decision-field label.selected { border-color: #49a47b; background: #edf9f2; box-shadow: 0 0 0 2px rgba(73, 164, 123, 0.1); }
.decision-field label.reject.selected { border-color: #dc746e; background: #fff3f2; box-shadow: 0 0 0 2px rgba(220, 116, 110, 0.1); }
.decision-field input { position: absolute; top: 18px; left: 15px; width: 17px; height: 17px; }
.decision-field small { line-height: 1.5; }
.enabled-control { display: flex; align-items: center; gap: 9px; height: 43px; padding: 0 12px; border: 1px solid #cfdee5; border-radius: 9px; }
.enabled-control input { width: 18px; height: 18px; }
.enabled-control strong { font-size: 13px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 9px; padding-top: 18px; border-top: 1px solid #e3ecef; }

@media (max-width: 1050px) {
  .overview-grid { grid-template-columns: 1fr; }
  .history-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .keyword-filter { grid-column: 1 / -1; }
  .reset-filter-btn { justify-self: end; }
}

@media (max-width: 720px) {
  .auto-audit-page { gap: 14px; }
  .page-header { align-items: stretch; padding: 21px 18px; flex-direction: column; }
  .create-rule-btn { width: 100%; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow-card,
  .rules-card,
  .history-card { padding: 18px 15px; }
  .workflow-steps { align-items: stretch; gap: 5px; }
  .workflow-steps div { font-size: 11px; }
  .workflow-steps i { width: 12px; margin-top: 17px; }
  .section-head,
  .history-head { align-items: stretch; flex-direction: column; }
  .rule-row { grid-template-columns: 62px minmax(0, 1fr); }
  .priority-block { grid-row: 1 / 3; }
  .rule-main { padding: 14px; }
  .rule-actions { grid-column: 2; justify-content: flex-end; flex-wrap: wrap; padding: 0 14px 14px; border: 0; }
  .history-filters { grid-template-columns: 1fr; }
  .keyword-filter { grid-column: auto; }
  .reset-filter-btn { width: 100%; justify-self: stretch; }
  .pagination-bar { align-items: stretch; flex-direction: column; }
  .pagination-controls { display: grid; grid-template-columns: repeat(2, 1fr); }
  .pagination-page-list { grid-column: 1 / -1; order: -1; overflow-x: auto; padding-bottom: 4px; }
  .modal-backdrop { align-items: end; padding: 10px; }
  .rule-modal { width: 100%; max-height: calc(100dvh - 20px); padding: 22px 16px; border-radius: 18px 18px 12px 12px; }
  .rule-form { grid-template-columns: 1fr; }
  .field-wide,
  .decision-field { grid-column: auto; }
  .decision-field { grid-template-columns: 1fr; }
  .modal-actions { position: sticky; bottom: -22px; margin: 0 -16px -22px; padding: 14px 16px; background: rgba(255,255,255,.97); }
}
</style>
