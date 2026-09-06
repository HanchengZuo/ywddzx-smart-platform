<template>
  <div class="deadline-management">
    <header class="surface hero"><div><span class="eyebrow">质安专属 · ROOT管理</span><h2>质安流程时限管理</h2><p>验收、申诉申请、两级审核，期限与处理依据全程留痕。</p></div><span class="version">规则 v{{ policy.version || 1 }}</span></header>
    <div class="scope surface"><strong>仅适用五张检查表</strong><p>计量稽查检查表（视频、现场）、环境无异味管理检查表（现场）、质量安全环保检查表（视频、现场）。其他检查表不受影响。</p></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="message" class="message" role="status">{{ message }}</p>
    <section class="surface">
      <div class="steps">
        <section v-for="(stage, index) in stages" :key="stage.key" :class="{ inactive: !policy[`${stage.key}_enabled`] }">
          <div class="stage-top"><span class="number">0{{ index + 1 }}</span>
            <button class="switch" type="button" role="switch" :aria-label="`${stage.title}时限`" :aria-checked="!!policy[`${stage.key}_enabled`]"
              :class="{ enabled: policy[`${stage.key}_enabled`] }" :disabled="saving || loading"
              @click="prepare(stage, !policy[`${stage.key}_enabled`])"><span class="switch-track"><i /></span>{{ policy[`${stage.key}_enabled`] ? '已启用' : '已关闭' }}</button>
          </div>
          <h3>{{ stage.title }}</h3><p class="state-copy">{{ policy[`${stage.key}_enabled`] ? stage.on : stage.off }}</p>
          <label>{{ stage.label }}（天）<input v-model.number="draft[`${stage.key}_days`]" type="number" min="1" max="365" :disabled="saving || loading" @change="prepare(stage, policy[`${stage.key}_enabled`])" /></label>
          <label v-if="stage.key === 'review'">启用后的超时处理<select v-model="draft.timeout_action" :disabled="saving || loading" @change="prepare(stage, policy.review_enabled)"><option value="manual">等待人工处理（仅计时提醒）</option><option value="approve">自动通过申诉，问题已销毁</option><option value="reject">自动拒绝申诉，恢复整改</option></select></label>
          <p>{{ stage.description }}</p>
        </section>
      </div>
      <div class="save-row"><div><strong>每项独立生效，无需统一“保存规则”</strong><p>关闭后，已有待办也不再受该项时限限制；重新启用时，尚未结束的任务从重新启用时刻获得完整期限。只调整天数或超时方式时，已有计时任务保持原设置，新任务使用新设置。</p><small>最后操作：{{ editor }} · {{ format(policy.updated_at) }}</small></div></div>
    </section>
    <section class="surface worker"><strong>低频后台处理</strong><span>扫描间隔：{{ scanMinutes }} 分钟</span><span>最近成功：{{ format(worker.last_success_at) }}</span><span>下次最早扫描：{{ format(worker.next_scan_at) }}</span><span v-if="worker.last_failure_at">最近失败：{{ format(worker.last_failure_at) }}</span><p>默认每3小时分批扫描一次，多进程共用调度时间，关闭的功能跳过业务扫描。自动处理允许延迟数小时，前端离开不影响处理；批次积压或失败时可能延后，请结合后台日志核查。</p></section>
    <section class="surface">
      <h3>时限与自动处理追溯</h3><p class="muted">留痕记录不是自动归责结论，请结合人员权限变更与实际工作安排核实。</p>
      <form class="filters" @submit.prevent="page = 1; loadEvents()"><select v-model="kind"><option value="">全部事件</option><option value="acceptance_timeout">超时自动验收</option><option value="review_timeout">申诉超时处理</option><option value="review_started">申诉审核开始</option><option value="review_handoff">转交质安部</option><option value="policy_updated">规则修改</option></select><input v-model="inspectionId" type="number" min="1" placeholder="巡检记录ID" aria-label="巡检记录ID" /><input v-model="issueId" type="number" min="1" placeholder="问题ID" aria-label="问题ID" /><button :disabled="eventsLoading">开始筛选</button></form>
      <p v-if="eventsLoading">正在加载记录…</p>
      <article v-for="event in events" :key="event.id" class="event">
        <header><strong>{{ eventLabels[event.kind] || event.kind }}</strong><time>{{ format(event.created_at) }}</time></header>
        <p>{{ event.detail }}</p><div class="meta">巡检记录 #{{ event.inspection_id || '—' }} · 问题 #{{ event.issue_id || '—' }} · 申诉 #{{ event.appeal_id || '—' }}</div>
        <details><summary>查看期限、规则和待处理人员</summary><p>阶段：{{ stageLabels[event.stage] || '规则配置' }} · 规则v{{ event.policy.version }}</p><p>截止：{{ format(event.deadline_at) }}</p><p>操作：{{ event.actor.real_name || event.actor.username || event.actor.name }}</p><p>阶段接收人员：{{ names(event.responsible.phase_start || event.responsible) }}</p><p v-if="event.responsible.at_timeout">截止时待办理人员：{{ names(event.responsible.at_timeout) }}</p><p>验收 {{ event.policy.acceptance_days }} 天 · 申请 {{ event.policy.appeal_days }} 天 · 审核 {{ event.policy.review_days }} 天 · 超时方式：{{ actionLabels[event.policy.timeout_action] }}</p></details>
      </article><p v-if="!eventsLoading && !events.length">暂无符合条件的记录。</p>
      <nav><button :disabled="page <= 1 || eventsLoading" @click="page--; loadEvents()">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }} · 共{{ total }}条</span><button :disabled="page * 20 >= total || eventsLoading" @click="page++; loadEvents()">下一页</button></nav>
    </section>
    <Teleport to="body"><div v-if="pending" class="confirm-overlay"><section class="surface confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><h3 id="confirm-title">{{ pending.title }}</h3><p>仅调整「{{ pending.stage.title }}」，不影响另外两个开关。</p><p>{{ pending.enabled ? `启用时限：${pending.days}天。` : '关闭后，该环节的已有待办也不再受时限限制，原有人工流程保持可用。' }}</p><p v-if="pending.stage.key === 'review' && pending.enabled">审核超时：<strong>{{ actionLabels[pending.timeout_action] }}</strong>。自动通过会将问题置为已销毁，请核实。</p><p v-if="pending.enabled && !policy[`${pending.stage.key}_enabled`]">重新启用将给予未结束的任务完整期限，不会立即处理旧的超时记录。</p><footer><button :disabled="saving" @click="cancel">取消</button><button class="primary" :disabled="saving" @click="save">{{ saving ? '处理中…' : '确认操作' }}</button></footer></section></div></Teleport>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
const policy = ref({}), draft = ref({}), editor = ref(''), worker = ref({}), scanMinutes = ref(180)
const loading = ref(true), saving = ref(false), pending = ref(null), error = ref(''), message = ref('')
const stages = [
  { key: 'acceptance', title: '站点签名验收', label: '验收时限', on: '到期后由后台分批自动验收', off: '不计时、不自动验收，等待站点人工签名', description: '检查人确认完成且全部问题审核结束后开始。自动验收留痕，不生成手写签名，可供考核追溯。' },
  { key: 'appeal', title: '站点发起申诉', label: '申诉申请时限', on: '到期关闭新申诉入口', off: '申诉不受天数限制，仍须满足申诉资格', description: '记录验收、问题进入待整改后开始。此开关不影响同一问题只能申诉一次的限制。' },
  { key: 'review', title: '片区与质安部共享审核', label: '共享审核时限', on: '两级共用期限，到期按选定方式处理', off: '不计时、不自动判定，继续人工审核', description: '从发起申诉开始，转交质安部不重新计时；系统处理记录当时停留阶段与待办理账号。' }
]
const events = ref([]), eventsLoading = ref(false), total = ref(0), page = ref(1), kind = ref(''), inspectionId = ref(''), issueId = ref('')
const actionLabels = { manual: '等待人工处理', approve: '自动通过申诉', reject: '自动拒绝申诉' }
const eventLabels = { acceptance_timeout: '系统超时自动验收', review_timeout: '系统申诉超时处理', review_started: '申诉审核计时开始', review_handoff: '转交质安部（期限不变）', policy_updated: 'root更新规则' }
const stageLabels = { acceptance: '站点签名验收', area_pending: '片区初审', quality_pending: '质安部终审' }
const format = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无'
const names = value => Array.isArray(value) && value.length ? value.map(u => `${u.real_name || u.username}（账号ID ${u.id}）`).join('、') : '无可用账号记录，需核查权限与安排'
function cancel() { pending.value = null; draft.value = { ...policy.value } }
function prepare(stage, enabled) {
  const days = draft.value[`${stage.key}_days`]
  if (!Number.isInteger(days) || days < 1 || days > 365) { error.value = '时限须为1至365的整数。'; return }
  error.value = ''
  pending.value = { stage, enabled, days, timeout_action: draft.value.timeout_action, title: enabled === policy.value[`${stage.key}_enabled`] ? '调整该项时限' : enabled ? '启用该项时限' : '关闭该项时限' }
}
async function load() {
  loading.value = true
  try { const { data } = await axios.get('/api/management/quality-deadlines'); policy.value = data.policy; draft.value = { ...data.policy }; editor.value = data.editor; worker.value = data.worker; scanMinutes.value = data.scan_interval_minutes }
  catch (err) { error.value = err.response?.data?.error || '时限配置读取失败。' }
  finally { loading.value = false }
}
async function save() {
  saving.value = true; error.value = ''; message.value = ''
  try {
    const change = pending.value
    await axios.put('/api/management/quality-deadlines', { stage: change.stage.key, enabled: change.enabled, days: change.days, timeout_action: change.timeout_action, version: policy.value.version })
    pending.value = null; message.value = `${change.stage.title}已更新，另外两个开关保持不变。`; await load(); await loadEvents()
  } catch (err) { error.value = err.response?.data?.error || '操作失败，请重试。'; cancel(); await load() }
  finally { saving.value = false }
}
async function loadEvents() {
  eventsLoading.value = true
  try { const { data } = await axios.get('/api/management/quality-deadlines/events', { params: { page: page.value, kind: kind.value, inspection_id: inspectionId.value, issue_id: issueId.value } }); events.value = data.items; total.value = data.total }
  catch (err) { error.value = err.response?.data?.error || '追溯记录读取失败。' }
  finally { eventsLoading.value = false }
}
onMounted(() => { load(); loadEvents() })
</script>
<style scoped>
.stage-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.steps section.inactive { background: #f8fafc; border-color: #e0e6ec; }.state-copy { min-height: 48px; color: #53718a; }.switch { display: flex; gap: 8px; align-items: center; padding: 8px; border: 0; background: transparent; white-space: nowrap; }.switch-track { width: 38px; height: 22px; border-radius: 20px; background: #93a5b4; padding: 3px; box-sizing: border-box; }.switch-track i { display: block; width: 16px; height: 16px; border-radius: 50%; background: white; transition: transform .15s ease; }.enabled .switch-track { background: #2186b6; }.enabled i { transform: translateX(16px); }button:focus-visible { outline: 3px solid #60a5df; outline-offset: 3px; }
.deadline-management { display: grid; gap: 20px; color: #23394f; }.surface { background: white; border: 1px solid #dce6f1; border-radius: 20px; padding: 24px; }.hero { display: flex; align-items: center; justify-content: space-between; background: radial-gradient(ellipse at right top,#ddecf6,transparent 70%),#fff; }.eyebrow,.muted,small { color: #668097; font-size: 12px; }.version,.number { background: #e9f3fa; border-radius: 12px; color: #287fae; padding: 10px; }.steps { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 20px; }.steps section { min-width: 0; border: 1px solid #e0e9f1; border-radius: 16px; padding: 20px; background: linear-gradient(135deg,#f5faff,#fff); }.number { display: inline-block; font-size: 20px; font-weight: 700; }h2,h3 { margin: 8px 0 14px; }p { line-height: 1.7; font-size: 14px; overflow-wrap: anywhere; }label { display: grid; gap: 8px; font-size: 14px; margin: 12px 0; }input,select { font: inherit; font-size: 16px; padding: 10px; border-radius: 10px; border: 1px solid #c8d7e4; min-width: 0; width: 100%; box-sizing: border-box; }button { padding: 10px 16px; border: 1px solid #c8d7e4; border-radius: 10px; background: white; color: #365770; cursor: pointer; }button:disabled { opacity: .5; cursor: default; }.primary { background: #217ba9; color: white; border-color: #217ba9; }.save-row { margin-top: 20px; padding-top: 16px; border-top: 1px solid #e2e9f0; display: flex; align-items: center; justify-content: space-between; gap: 18px; }.worker { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }.worker p { width: 100%; margin: 0; color: #687f94; }.filters { display: flex; gap: 10px; flex-wrap: wrap; }.filters input,.filters select { width: min(200px,100%); }.event { border: 1px solid #e0e8f0; border-radius: 14px; margin-top: 14px; padding: 16px; }.event header,nav,footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }time,.meta { font-size: 12px; color: #6c8195; }details { margin-top: 12px; }summary { cursor: pointer; color: #267da8; }nav { margin-top: 20px; align-items: center; justify-content: center; }.error { color: #b42318; }.message { color: #22775d; }.confirm-overlay { position: fixed; inset: 0; background: #13263b99; z-index: 4500; display: grid; place-items: center; padding: 18px; }.confirm { max-width: 540px; }footer { justify-content: flex-end; }@media(max-width:900px) { .steps { grid-template-columns: 1fr; }.surface { padding: 16px; }.save-row { flex-direction: column; align-items: stretch; } }
</style>
