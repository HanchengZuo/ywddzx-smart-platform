<template>
  <div class="appeals-page">
    <header class="surface page-heading"><div><span class="eyebrow">巡检系统</span><h2>申诉空间</h2><p>站点发起 → 所属片区初审 → 授权质安部终审</p></div><span class="scope-note">仅展示当前账号可查看的数据</span></header>
    <div v-if="notice" class="notice" role="status">{{ notice }}<button @click="notice = ''" aria-label="关闭提示">×</button></div>
    <form class="surface filters" @submit.prevent="page = 1; load()">
      <div class="tabs"><button type="button" :class="{ active: !archive }" @click="setArchive(false)">待处理申诉 <span v-if="counts.active" class="count-badge">{{ counts.active }}</span></button><button type="button" :class="{ active: archive }" @click="setArchive(true)">已结束记录 <span v-if="counts.unread_ended" class="count-badge">{{ counts.unread_ended }}</span></button></div>
      <label>搜索问题或站点<input v-model="keyword" placeholder="问题ID、站点名称、问题描述" /></label><button class="primary" :disabled="loading">开始筛选</button>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <section :aria-busy="loading" class="results">
      <div v-if="loading" class="surface empty" role="status">正在加载申诉记录…</div>
      <template v-else>
        <p class="count">共 {{ total }} 条{{ archive ? '已结束记录，点击“查看处理结果”逐条消除本账号未读提醒' : '进行中申诉，查看不会消除数量提醒，结束后转为未读结果' }}。每个问题仅允许申诉一次。</p>
        <article v-for="item in items" :key="item.id" class="surface appeal-card">
          <header><div><span class="eyebrow">问题 #{{ item.issue_id }} · 申诉 #{{ item.id }}</span><h3>{{ item.region }} · {{ item.station_name }}</h3><p class="muted">{{ item.table_name }} · 检查时间 {{ item.inspection_time }}</p></div><span class="status" :class="item.status">{{ labels[item.status] }}</span></header>
          <div class="issue-content"><p>{{ item.description }}</p><button v-if="item.photo_path" class="photo" @click="photo = imageUrl(item.photo_path)"><img :src="imageUrl(item.photo_path)" alt="问题照片，点击放大" loading="lazy" /></button></div>
          <WorkflowDeadline v-if="!archive && item.review_deadline_ms" :deadline="item.review_deadline_ms" :server-now="item.server_now_ms"
            :title="item.status === 'area_pending' ? '片区独立审核倒计时' : '质安部独立审核倒计时'" :hint="reviewDeadlineHint(item)" :expired-hint="reviewDeadlineHint(item, true)" @expired="expiredReviews.add(reviewDeadlineKey(item))" />
          <p v-if="!archive && item.review_deadline_enabled && !item.review_deadline_ms" class="outcome">本阶段截止时间待同步，可能缺少对应年份工作日历。暂不自动判定，仍可人工审核。</p>
          <p v-if="item.timeout_at" class="outcome">本申诉由系统按超时规则处理，并非人员主动审核。{{ item.timeout_stage === 'area_pending' ? item.area_reason : item.quality_reason }}</p>
          <button v-if="archive" class="result-toggle" :aria-expanded="expanded.has(item.id)" :disabled="reading !== null" @click="viewResult(item)">{{ expanded.has(item.id) ? '收起处理结果' : '查看处理结果' }} <span v-if="item.unread" class="count-badge">未读</span></button>
          <AppealProgress v-if="!archive || expanded.has(item.id)" :item="item" :reviewers="qualityReviewers" />
          <footer><span class="muted">当前问题状态：{{ item.issue_status }}</span><button v-if="item.can_decide" class="primary" :disabled="item.review_deadline_enabled && expiredReviews.has(reviewDeadlineKey(item)) && item.review_policy?.timeout_action !== 'manual'" @click="openDecision(item)">审核申诉</button><span v-else-if="!archive" class="muted">当前账号在此阶段仅可查看</span></footer>
        </article>
        <div v-if="!items.length" class="surface empty">暂无符合条件的申诉</div>
      </template>
    </section>
    <nav class="pagination" aria-label="申诉分页"><button :disabled="loading || page <= 1" @click="page--; load()">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span><button :disabled="loading || page * 20 >= total" @click="page++; load()">下一页</button></nav>
    <Teleport to="body">
      <div v-if="selected" class="overlay" @click.self="!saving && (selected = null)">
        <form class="decision surface" role="dialog" aria-modal="true" aria-labelledby="decision-title" @submit.prevent="decide">
          <h3 id="decision-title">{{ selected.status === 'area_pending' ? '片区初审' : '质安部终审' }} · 问题 #{{ selected.issue_id }}</h3>
          <p class="muted">{{ selected.station_name }} · {{ selected.reason }}</p>
          <label>审核决定<select v-model="decision" :disabled="saving"><option value="">请选择</option><option value="approve">通过申诉</option><option value="reject">拒绝申诉</option></select></label>
          <p class="outcome">{{ decision === 'reject' ? '问题将离开待处理申诉，回到站点继续整改。' : selected.status === 'area_pending' ? '通过后转交授权质安部账号终审，仍暂停整改。' : '通过后问题状态为已销毁，不再要求整改，历史记录保留。' }}</p>
          <label>审核原因（必填）<textarea v-model="reason" rows="5" maxlength="4000" :disabled="saving" placeholder="说明判断依据，便于站点了解处理结果"></textarea></label>
          <p v-if="decisionError" class="error" role="alert">{{ decisionError }}</p>
          <footer><button type="button" :disabled="saving" @click="selected = null">取消</button><button class="primary" :disabled="saving || !decision || !reason.trim()">{{ saving ? '正在提交…' : '确认提交审核结果' }}</button></footer>
        </form>
      </div>
      <div v-if="photo" class="overlay photo-overlay" role="dialog" aria-label="问题照片预览" @click="photo = ''"><button aria-label="关闭照片">关闭</button><img :src="photo" alt="完整问题照片" @click.stop /></div>
    </Teleport>
  </div>
</template>
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import AppealProgress from '../../components/AppealProgress.vue'
import WorkflowDeadline from '../../components/WorkflowDeadline.vue'
const expiredReviews = ref(new Set())
const reviewDeadlineKey = item => `${item.id}:${item.review_deadline_ms}`
const reviewDeadlineHint = (item, expired = false) => {
  const action = item.review_policy?.timeout_action
  return `${expired ? '期限已结束，等待低频后台任务处理。' : '各级独立计时，非工作日暂停。'}${action === 'approve' ? (item.status === 'area_pending' ? '超时自动通过片区初审，转交质安部重新计时。' : '超时自动通过终审，问题已销毁。') : action === 'reject' ? '系统按期扫描时自动拒绝申诉，恢复整改。' : '当前规则不自动决策，仍需人工审核。'} 自动处理可能延后数小时，超时阶段及待办理账号均留痕。`
}
const route = useRoute()
const router = useRouter()
const items = ref([]), total = ref(0), page = ref(1), archive = ref(false), keyword = ref('')
const counts = ref({ active: 0, unread_ended: 0, total: 0 }), expanded = ref(new Set()), reading = ref(null), qualityReviewers = ref([])
const loading = ref(false), error = ref(''), notice = ref(''), selected = ref(null), decision = ref(''), reason = ref(''), saving = ref(false), decisionError = ref(''), photo = ref('')
const labels = { area_pending: '待片区初审', quality_pending: '待质安部终审', approved: '申诉通过', rejected: '申诉被拒绝', cancelled: '申诉已取消' }
const imageUrl = path => !path ? '' : /^https?:\/\//.test(path) || path.startsWith('/storage/') ? path : `/storage/${path.replace(/^\//, '')}`
let requestId = 0
async function load() {
  const id = ++requestId
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/issue-appeals', { params: { page: page.value, archive: archive.value ? 1 : 0, keyword: keyword.value } })
    if (id !== requestId) return
    items.value = data.items
    total.value = data.total
    counts.value = data.counts
    qualityReviewers.value = data.quality_reviewers || []
  } catch (err) { if (id === requestId) error.value = err.response?.data?.error || '申诉记录读取失败。' }
  finally { if (id === requestId) loading.value = false }
}
function setArchive(value) { archive.value = value; page.value = 1; load() }
async function viewResult(item) {
  if (reading.value !== null) return
  if (expanded.value.has(item.id)) { expanded.value.delete(item.id); return }
  expanded.value.add(item.id)
  if (!item.unread) return
  reading.value = item.id
  try {
    const { data } = await axios.post(`/api/issue-appeals/${item.id}/read`, { version: item.notification_version })
    item.unread = false
    counts.value = data.counts
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
  } catch (err) {
    expanded.value.delete(item.id)
    error.value = err.response?.data?.error || '标记已读失败，请重新查看。'
  } finally { reading.value = null }
}
function openDecision(item) { selected.value = item; decision.value = ''; reason.value = ''; decisionError.value = '' }
async function decide() {
  if (saving.value || !decision.value || !reason.value.trim()) return
  saving.value = true
  decisionError.value = ''
  try {
    const { data } = await axios.post(`/api/issue-appeals/${selected.value.id}/decision`, { decision: decision.value, reason: reason.value.trim(), stage: selected.value.status })
    notice.value = data.message
    selected.value = null
    window.dispatchEvent(new Event('my-pending-rectification-refresh'))
    await load()
  } catch (err) { decisionError.value = err.response?.data?.error || '审核提交失败。' }
  finally { saving.value = false }
}
function keydown(event) { if (event.key === 'Escape') { photo.value = ''; if (!saving.value) selected.value = null } }
onMounted(() => {
  if (route.query.submitted === '1') { notice.value = '问题已进入申诉空间，等待所属片区审核反馈。'; router.replace({ path: route.path, query: {} }) }
  load()
  window.addEventListener('keydown', keydown)
})
onBeforeUnmount(() => { requestId++; window.removeEventListener('keydown', keydown) })
</script>
<style scoped>
.appeals-page { display: grid; gap: 20px; color: #17283f; }
.surface { background: #fff; border: 1px solid #dce6f1; border-radius: 20px; padding: 24px; box-shadow: 0 8px 24px #20385d06; }
.page-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; background: linear-gradient(115deg, #fff, #edf5fc); }
.eyebrow { color: #367ca5; font-size: 12px; letter-spacing: .06em; }
h2,h3 { margin: 8px 0; } p { line-height: 1.7; overflow-wrap: anywhere; white-space: pre-wrap; }
.scope-note,.muted,.count { color: #64748b; font-size: 13px; }
.filters { display: flex; align-items: end; flex-wrap: wrap; gap: 16px; }
.tabs { display: flex; gap: 6px; align-self: center; }
.tabs button { display: inline-flex; align-items: center; gap: 8px; }
.count-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 20px; padding: 2px 6px; border-radius: 20px; background: #dc3545; color: white; font-size: 12px; line-height: 1.5; }
.result-toggle { margin: 8px 0 18px; display: flex; align-items: center; gap: 12px; }
button { border: 1px solid #cbd9e7; background: white; color: #294862; border-radius: 10px; padding: 10px 16px; cursor: pointer; font: inherit; font-size: 14px; }
button:disabled { opacity: .5; cursor: default; } .primary,.tabs .active { background: #1976ac; border-color: #1976ac; color: white; }
label { display: grid; gap: 8px; font-size: 14px; } input,select,textarea { font: inherit; font-size: 16px; border: 1px solid #cbd9e7; padding: 10px; border-radius: 10px; box-sizing: border-box; width: 100%; }
.filters label { flex: 1; min-width: 200px; } .results { display: grid; gap: 18px; }
.appeal-card header,.appeal-card footer { display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap; }
.status { padding: 8px 12px; font-size: 13px; border-radius: 24px; background: #edf5fc; color: #276e9e; }
.status.rejected { color: #b15b20; background: #fff4e8; } .status.approved { color: #21715a; background: #eaf7f0; }
.issue-content { display: flex; gap: 20px; align-items: start; } .issue-content p { flex: 1; }
.photo { padding: 4px; width: 140px; height: 110px; cursor: zoom-in; } .photo img { width: 100%; height: 100%; object-fit: contain; }
.pagination { display: flex; gap: 16px; justify-content: center; align-items: center; } .empty { padding: 48px; text-align: center; color: #64748b; }
.notice,.outcome { background: #eaf5fd; color: #246187; padding: 14px; border-radius: 12px; } .notice { display: flex; justify-content: space-between; align-items: center; } .notice button { border: 0; background: none; }
.error { color: #b42318; } .overlay { position: fixed; inset: 0; z-index: 4000; background: #13223a99; display: grid; place-items: center; padding: 20px; }
.decision { width: min(580px,100%); max-height: 90dvh; overflow-y: auto; box-sizing: border-box; } .decision footer { display: flex; gap: 10px; justify-content: end; margin-top: 18px; }
.photo-overlay img { max-width: 95vw; max-height: 86dvh; object-fit: contain; } .photo-overlay > button { position: absolute; top: 20px; right: 20px; }
@media(max-width:700px) { .surface { padding: 16px; } .page-heading,.issue-content { flex-direction: column; align-items: start; } .tabs { width: 100%; } .scope-note { display: none; } }
</style>
