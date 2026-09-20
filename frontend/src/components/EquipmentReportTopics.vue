<template>
  <section class="equipment-topics">
    <header><div><small>EQUIPMENT ANALYSIS</small><h3>设备设施选题与依据</h3>
      <p>高频问题由 AI 选题，原因引用规范参考表；特性、严重问题允许人工调整。保存后重新生成生效。</p></div>
      <span>全局共享</span></header>
    <p v-if="error" role="alert" class="error">{{ error }} <button @click="load">重试读取</button></p>
    <p v-else-if="loading">正在读取选题依据...</p>
    <div class="topic-cards">
      <button v-for="item in tabs" :key="item.key" @click="open(item.key)">
        <small>{{ item.label }}</small><strong>{{ count(item.key) }}</strong><span>{{ item.key === 'high' ? '查看类别、原因与关联证据' : '查看与调整选中问题' }}</span>
      </button>
    </div>
    <p v-if="!analysis.generated">首次生成后展示 AI 选题；可先手动设置特性、严重问题。</p>
    <p v-else>AI选题来源：{{ analysis.source_generated_at || '最近生成报告' }}。问题库变化后需重新生成更新AI选题。</p>
    <p v-for="warning in analysis.selection_warnings || []" :key="warning" role="alert" class="error">{{ warning }}</p>
    <small>{{ savedLabel }}</small>
    <Teleport to="body">
      <div v-if="active" class="equipment-topic-overlay" @click.self="close">
        <section role="dialog" aria-modal="true" :aria-label="activeTitle" class="equipment-topic-dialog">
          <header><div><small>选题依据 · {{ active === 'high' ? '只读' : '可编辑' }}</small><h3>{{ activeTitle }}</h3></div><button :disabled="saving" @click="close">关闭</button></header>
          <p v-if="error" role="alert" class="error">{{ error }}</p>
          <template v-if="active === 'high'">
            <p>问题产生原因逐字引用 Excel；AI 不生成原因。展开可核查所有关联问题。</p>
            <details v-for="group in analysis.high_groups || []" :key="group.phrase">
              <summary>{{ group.phrase }} · {{ group.issues.length }} 项</summary>
              <p class="cause">{{ group.causes.join('\n') }}</p>
              <article v-for="issue in group.issues" :key="issue.issue_id"><b>#{{ issue.issue_id }} · {{ issue.station_name }}</b><p>{{ issue.description }}</p>
                <button v-if="issue.issue_photo" class="photo" @click="$emit('photo', issue)"><img :src="resolveImage(issue.issue_photo)" alt="问题照片" loading="lazy" /></button>
              </article>
            </details>
            <p v-if="!analysis.high_groups?.length">暂无高频选题结果，不以固定示例代替实际问题。</p>
          </template>
          <template v-else>
            <div class="filters"><input v-model="keyword" placeholder="搜索ID、站点、问题描述或短语" type="search" />
              <select v-model="unit"><option value="">全部片区</option><option v-for="name in units" :key="name">{{ name }}</option></select>
              <label><input v-model="selectedOnly" type="checkbox" />仅看已选</label>
            </div>
            <p>已选 {{ draft[active].length }} 项。{{ active === 'special' ? '高频类别下的问题不可选为特性问题。' : '请依据实际风险判断，可取消AI选题或补选问题。' }}</p>
            <article v-for="issue in visibleIssues" :key="issue.issue_id">
              <label><input v-model="draft[active]" type="checkbox" :value="issue.issue_id" :disabled="active === 'special' && highIds.has(issue.issue_id)" />
                <b>#{{ issue.issue_id }} · {{ issue.management_unit }} · {{ issue.station_name }}</b></label>
              <small>{{ issue.phrase }} <em v-if="highIds.has(issue.issue_id)">高频类别</em></small><p>{{ issue.description }}</p>
              <button v-if="issue.issue_photo" class="photo" @click="$emit('photo', issue)"><img :src="resolveImage(issue.issue_photo)" alt="问题照片" loading="lazy" /></button>
            </article>
            <p v-if="!visibleIssues.length">没有符合当前筛选的问题。</p>
            <footer><span>只保存选题，不调用AI，不自动修改当前成稿。</span><button :disabled="saving || loading" @click="save">{{ saving ? '正在保存...' : '保存选题' }}</button></footer>
          </template>
        </section>
      </div>
    </Teleport>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
const props = defineProps({ month: String, dateFrom: String, dateTo: String, generatedAt: String,
  librarySignature: String, savedLabel: String, resolveImage: { type: Function, required: true } })
const emit = defineEmits(['change', 'saved', 'photo'])
const analysis = ref({}), loading = ref(false), saving = ref(false), error = ref(''), active = ref('')
const keyword = ref(''), unit = ref(''), selectedOnly = ref(false), draft = ref({ special: [], severe: [] })
let requestId = 0
const tabs = [{ key: 'high', label: '高频问题 / 规范原因' }, { key: 'special', label: '特性问题' }, { key: 'severe', label: '严重问题' }]
const activeTitle = computed(() => tabs.find(t => t.key === active.value)?.label || '')
const highIds = computed(() => new Set((analysis.value.high_groups || []).flatMap(g => g.issues.map(i => i.issue_id))))
const units = computed(() => [...new Set((analysis.value.issues || []).map(i => i.management_unit))])
const visibleIssues = computed(() => (analysis.value.issues || []).filter(i =>
  (!unit.value || i.management_unit === unit.value) && (!selectedOnly.value || draft.value[active.value]?.includes(i.issue_id)) &&
  `${i.issue_id} ${i.station_name} ${i.description} ${i.phrase}`.includes(keyword.value.trim())))
const count = key => key === 'high' ? (analysis.value.high_groups || []).length : (analysis.value[key+'_issue_ids'] || []).length
const params = () => ({ month: props.month, date_from: props.dateFrom, date_to: props.dateTo })
function adopt(value) {
  analysis.value = value
  draft.value = { special: [...(value.special_issue_ids || [])], severe: [...(value.severe_issue_ids || [])] }
  emit('change', value)
}
async function load() {
  const id = ++requestId
  active.value = ''
  emit('change', null)
  if (!props.dateFrom || !props.dateTo) { loading.value = false; analysis.value = {}; return }
  loading.value = true; error.value = ''
  try {
    const response = await axios.get('/api/inspection-reports/equipment-analysis', { params: params() })
    if (id === requestId) adopt(response.data.analysis || {})
  } catch (err) {
    if (id === requestId) error.value = err.response?.data?.error || '选题读取失败。'
  } finally { if (id === requestId) loading.value = false }
}
function open(key) {
  if (loading.value || error.value) return
  draft.value = { special: [...(analysis.value.special_issue_ids || [])], severe: [...(analysis.value.severe_issue_ids || [])] }
  active.value = key; keyword.value = ''; unit.value = ''; selectedOnly.value = false
}
function close() { if (!saving.value) active.value = '' }
async function save() {
  const id = requestId
  saving.value = true; error.value = ''
  try {
    const response = await axios.put('/api/inspection-reports/equipment-analysis', { ...params(),
      special_issue_ids: draft.value.special, severe_issue_ids: draft.value.severe })
    if (id === requestId) { adopt(response.data.analysis); active.value = ''; emit('saved') }
  } catch (err) { if (id === requestId) error.value = err.response?.data?.error || '保存失败。' }
  finally { saving.value = false }
}
watch(() => [props.month, props.dateFrom, props.dateTo, props.generatedAt, props.librarySignature], load, { immediate: true })
onBeforeUnmount(() => { requestId++ })
</script>

<style scoped>
.equipment-topics{padding:22px;border:1px solid #d7e5ef;border-radius:18px;background:linear-gradient(120deg,#f5faff,#fff)}
header{display:flex;justify-content:space-between;align-items:center;gap:16px}h3{margin:6px 0;color:#153c56}small{color:#607d91}p{line-height:1.65;color:#475569;white-space:pre-wrap}.topic-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}.topic-cards button{display:flex;flex-direction:column;align-items:flex-start;gap:9px;padding:18px;background:#fff;border:1px solid #d6e3ec;border-radius:14px;text-align:left}.topic-cards strong{font-size:30px;color:#116c98}.topic-cards span{font-size:12px;color:#526b7b}button{cursor:pointer;border-radius:9px;border:1px solid #bdcedb;padding:8px 14px;background:white;color:#175a80}button:disabled{opacity:.5;cursor:wait}.error{color:#b42318}.equipment-topic-overlay{position:fixed;inset:0;background:#10293b99;z-index:1300;display:grid;place-items:center;padding:20px}.equipment-topic-dialog{width:min(1040px,100%);max-height:88vh;overflow:auto;background:white;border-radius:20px;padding:24px;box-shadow:0 24px 90px #10293b55}.equipment-topic-dialog header{position:sticky;top:-24px;background:white;padding:15px 0;z-index:1;border-bottom:1px solid #e1e9ee}details,article{border:1px solid #dce7ee;border-radius:12px;padding:14px;margin:12px 0}summary{cursor:pointer;color:#174d70;font-weight:700}.cause{background:#f1f6fa;padding:14px;border-radius:9px}article small{display:block;margin-top:8px}.filters{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.filters input[type=search]{flex:1;min-width:200px}.filters input,.filters select{padding:10px;border:1px solid #c7d7e4;border-radius:8px;font-size:16px}.photo{padding:4px;margin-top:8px}.photo img{width:140px;height:110px;object-fit:contain;border-radius:8px}footer{position:sticky;bottom:-24px;display:flex;justify-content:space-between;gap:12px;padding:18px 0;background:white;border-top:1px solid #dce7ee}footer button{background:#126e9b;color:white}footer span{font-size:12px;color:#607d91}em{color:#a56500;margin-left:10px}@media(max-width:640px){.topic-cards{grid-template-columns:1fr}.equipment-topic-overlay{padding:8px}.equipment-topic-dialog{padding:16px;border-radius:14px;max-height:94vh}header{align-items:flex-start}footer{flex-direction:column}.filters{flex-direction:column}}
</style>
