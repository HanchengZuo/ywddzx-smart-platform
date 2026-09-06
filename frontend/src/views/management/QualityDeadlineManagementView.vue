<template>
  <div class="deadline-management">
    <header class="surface hero"><div><span class="eyebrow">质安专属 · ROOT管理</span><h2>质安流程时限管理</h2><p>验收、申诉申请、两级审核，期限与处理依据全程留痕。</p></div><span class="version">规则 v{{ policy.version || 1 }}</span></header>
    <div class="scope surface"><strong>仅适用五张检查表</strong><p>计量稽查检查表（视频、现场）、环境无异味管理检查表（现场）、质量安全环保检查表（视频、现场）。其他检查表不受影响。</p></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="message" class="message" role="status">{{ message }}</p>
    <form class="surface" @submit.prevent="confirming = true">
      <div class="steps">
        <section><span class="number">01</span><h3>站点签名验收</h3><label>验收时限（天）<input v-model.number="policy.acceptance_days" type="number" min="1" max="365" required /></label><p>检查人确认完成且全部问题审核结束后开始。到期自动验收，不生成手写签名；可供事业部考核追溯。</p></section>
        <section><span class="number">02</span><h3>站点发起申诉</h3><label>申诉申请时限（天）<input v-model.number="policy.appeal_days" type="number" min="1" max="365" required /></label><p>记录验收后，问题进入待整改时开始。到期仅关闭申诉入口，不代替整改；同一问题仍限一次申诉。</p></section>
        <section><span class="number">03</span><h3>片区与质安部共享审核</h3><label>共享审核时限（天）<input v-model.number="policy.review_days" type="number" min="1" max="365" required /></label><label>超时处理<select v-model="policy.timeout_action"><option value="manual">待人工处理（不自动决策）</option><option value="approve">自动通过申诉，问题已销毁</option><option value="reject">自动拒绝申诉，恢复整改</option></select></label><p>从发起申诉开始，转交质安部不会重新计时。到期时停留在哪一阶段，就记录该阶段待办理账号。</p></section>
      </div>
      <div class="save-row"><div><strong>新规则只对后续新进入环节的任务生效</strong><p>已有任务按原规则快照继续计时，不会因修改配置提前到期。首次上线存量待办从启用时刻获得完整期限。</p><small>最后保存：{{ editor }} · {{ format(policy.updated_at) }}</small></div><button class="primary" :disabled="saving || loading">保存规则</button></div>
    </form>
    <section class="surface worker"><strong>后台时限任务</strong><span>最近成功扫描：{{ format(worker.last_success_at) }}</span><span v-if="worker.last_failure_at">最近失败：{{ format(worker.last_failure_at) }}（后台自动重试）</span><p>服务运行时约每30秒扫描，前端离开不影响处理。若长时间未成功扫描，请检查后端运行日志。</p></section>
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
    <Teleport to="body"><div v-if="confirming" class="confirm-overlay"><section class="surface confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><h3 id="confirm-title">确认保存时限规则</h3><p>后续新任务：验收 {{ policy.acceptance_days }} 天，申诉申请 {{ policy.appeal_days }} 天，共享审核 {{ policy.review_days }} 天。</p><p>申诉审核超时：<strong>{{ actionLabels[policy.timeout_action] }}</strong>。自动通过会将问题置为已销毁，请核实。</p><p>已有任务的期限与超时方式保持不变。</p><footer><button :disabled="saving" @click="confirming = false">取消</button><button class="primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '确认保存' }}</button></footer></section></div></Teleport>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
const policy = ref({}), editor = ref(''), worker = ref({}), loading = ref(false), saving = ref(false), confirming = ref(false), error = ref(''), message = ref('')
const events = ref([]), eventsLoading = ref(false), total = ref(0), page = ref(1), kind = ref(''), inspectionId = ref(''), issueId = ref('')
const actionLabels = { manual: '等待人工处理', approve: '自动通过申诉', reject: '自动拒绝申诉' }
const eventLabels = { acceptance_timeout: '系统超时自动验收', review_timeout: '系统申诉超时处理', review_started: '申诉审核计时开始', review_handoff: '转交质安部（期限不变）', policy_updated: 'root更新规则' }
const stageLabels = { acceptance: '站点签名验收', area_pending: '片区初审', quality_pending: '质安部终审' }
const format = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无'
const names = value => Array.isArray(value) && value.length ? value.map(u => `${u.real_name || u.username}（账号ID ${u.id}）`).join('、') : '无可用账号记录，需核查权限与安排'
async function load() {
  loading.value = true
  try { const { data } = await axios.get('/api/management/quality-deadlines'); policy.value = data.policy; editor.value = data.editor; worker.value = data.worker }
  catch (err) { error.value = err.response?.data?.error || '时限配置读取失败。' }
  finally { loading.value = false }
}
async function save() {
  saving.value = true; error.value = ''; message.value = ''
  try { await axios.put('/api/management/quality-deadlines', policy.value); confirming.value = false; message.value = '新规则已保存，后续新任务按此规则执行。'; await load(); await loadEvents() }
  catch (err) { error.value = err.response?.data?.error || '保存失败，请重试。'; confirming.value = false }
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
.deadline-management { display: grid; gap: 20px; color: #23394f; }.surface { background: white; border: 1px solid #dce6f1; border-radius: 20px; padding: 24px; }.hero { display: flex; align-items: center; justify-content: space-between; background: radial-gradient(ellipse at right top,#ddecf6,transparent 70%),#fff; }.eyebrow,.muted,small { color: #668097; font-size: 12px; }.version,.number { background: #e9f3fa; border-radius: 12px; color: #287fae; padding: 10px; }.steps { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 20px; }.steps section { min-width: 0; border: 1px solid #e0e9f1; border-radius: 16px; padding: 20px; background: linear-gradient(135deg,#f5faff,#fff); }.number { display: inline-block; font-size: 20px; font-weight: 700; }h2,h3 { margin: 8px 0 14px; }p { line-height: 1.7; font-size: 14px; overflow-wrap: anywhere; }label { display: grid; gap: 8px; font-size: 14px; margin: 12px 0; }input,select { font: inherit; font-size: 16px; padding: 10px; border-radius: 10px; border: 1px solid #c8d7e4; min-width: 0; width: 100%; box-sizing: border-box; }button { padding: 10px 16px; border: 1px solid #c8d7e4; border-radius: 10px; background: white; color: #365770; cursor: pointer; }button:disabled { opacity: .5; cursor: default; }.primary { background: #217ba9; color: white; border-color: #217ba9; }.save-row { margin-top: 20px; padding-top: 16px; border-top: 1px solid #e2e9f0; display: flex; align-items: center; justify-content: space-between; gap: 18px; }.worker { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }.worker p { width: 100%; margin: 0; color: #687f94; }.filters { display: flex; gap: 10px; flex-wrap: wrap; }.filters input,.filters select { width: min(200px,100%); }.event { border: 1px solid #e0e8f0; border-radius: 14px; margin-top: 14px; padding: 16px; }.event header,nav,footer { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }time,.meta { font-size: 12px; color: #6c8195; }details { margin-top: 12px; }summary { cursor: pointer; color: #267da8; }nav { margin-top: 20px; align-items: center; justify-content: center; }.error { color: #b42318; }.message { color: #22775d; }.confirm-overlay { position: fixed; inset: 0; background: #13263b99; z-index: 4500; display: grid; place-items: center; padding: 18px; }.confirm { max-width: 540px; }footer { justify-content: flex-end; }@media(max-width:900px) { .steps { grid-template-columns: 1fr; }.surface { padding: 16px; }.save-row { flex-direction: column; align-items: stretch; } }
</style>
