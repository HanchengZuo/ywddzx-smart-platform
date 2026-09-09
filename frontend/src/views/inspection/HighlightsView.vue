<template>
  <div class="page-shell highlights-page">
    <header class="page-header card-surface">
      <div><div class="eyebrow">现场经验 · 独立审核</div><h2>亮点列表</h2><p class="page-desc">记录值得推广的现场做法。仅审核通过的记录确认为亮点，不进入巡检记录与整改复核。</p></div>
    </header>
    <form class="card-surface filters" @submit.prevent="apply">
      <div class="filter-grid">
        <label v-for="field in textFields" :key="field.key" :class="{ selected: draft[field.key] }">{{ field.label }}<input v-model.trim="draft[field.key]" :placeholder="field.placeholder || '不限'" /></label>
        <label v-for="field in optionFields" :key="field.key" :class="{ selected: draft[field.key] }">{{ field.label }}<select v-model="draft[field.key]"><option value="">全部</option><option v-for="option in options[field.options] || []" :key="option">{{ option }}</option></select></label>
        <label :class="{ selected: draft.status }">亮点状态<select v-model="draft.status"><option value="">全部</option><option v-for="(label,key) in labels" :key="key" :value="key">{{ label }}</option></select></label>
        <label :class="{ selected: draft.date_from }">开始日期<input v-model="draft.date_from" type="date" /></label>
        <label :class="{ selected: draft.date_to }">结束日期<input v-model="draft.date_to" type="date" /></label>
      </div>
      <p class="filter-note">{{ dirty ? '筛选条件已调整，点击“开始筛选”后生效。' : '当前清单按已应用条件查询，每次只加载当前页。' }}</p>
      <div class="actions"><button type="button" class="btn btn-secondary" @click="draft = emptyFilters()">清空条件</button><button class="btn btn-primary" :disabled="loading">{{ loading ? '筛选中…' : '开始筛选' }}</button></div>
      <p v-if="optionsError" role="alert">{{ optionsError }} <button type="button" class="btn btn-secondary" @click="loadOptions">重试</button></p>
    </form>
    <p v-if="message" class="notice card-surface" role="status">{{ message }}</p>
    <section class="card-surface results" :aria-busy="loading">
      <div class="result-heading"><h3>亮点清单 <small>共 {{ total }} 条</small></h3><span>HL 独立编号</span></div>
      <p v-if="loading" class="empty" role="status">正在加载当前页亮点…</p>
      <p v-else-if="!rows.length" class="empty">当前条件下暂无亮点记录</p>
      <div v-else>
        <div class="desktop-table"><table><thead><tr><th>亮点ID</th><th v-for="column in columns" :key="column.key">{{ column.label }}</th><th>亮点照片</th><th>亮点状态</th><th>审核</th><th>操作</th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.id"><td><strong>{{ row.display_id }}</strong></td><td v-for="column in columns" :key="column.key" :class="{ description: column.key === 'description' }">{{ row[column.key] || '—' }}</td>
            <td><button class="photo" @click="preview = image(row.photo_path)"><img :src="image(row.photo_path)" loading="lazy" alt="亮点照片，点击放大" /></button></td>
            <td><span class="status" :class="row.audit_status">{{ labels[row.audit_status] }}</span></td><td>{{ row.audited_by_name || '待审核' }}<br />{{ formatTime(row.audited_at) }}<p v-if="row.audit_note">{{ row.audit_note }}</p></td>
            <td><div class="actions" v-if="row.can_audit"><button v-for="action in auditActions(row)" :key="action.key" class="btn" :class="action.key === 'approve' ? 'btn-primary' : 'btn-secondary'" :disabled="busy.has(row.id)" @click="decision = { row, action: action.key, label: action.label, note: '' }">{{ busy.has(row.id) ? '处理中' : action.label }}</button></div><span v-else>只读</span></td>
          </tr></tbody></table></div>
        <div class="mobile-cards"><article v-for="row in rows" :key="row.id" class="highlight-card"><header><strong>{{ row.display_id }} · {{ row.station }}</strong><span class="status" :class="row.audit_status">{{ labels[row.audit_status] }}</span></header>
          <p class="description">{{ row.description }}</p><button class="photo" @click="preview = image(row.photo_path)"><img :src="image(row.photo_path)" loading="lazy" alt="亮点照片，点击放大" /></button>
          <dl><template v-for="column in columns.filter(c => c.key !== 'description')" :key="column.key"><dt>{{ column.label }}</dt><dd>{{ row[column.key] || '—' }}</dd></template><dt>审核人员</dt><dd>{{ row.audited_by_name || '待审核' }}</dd><dt>审核时间</dt><dd>{{ formatTime(row.audited_at) || '—' }}</dd><dt>审核说明</dt><dd>{{ row.audit_note || '—' }}</dd></dl>
          <div class="actions" v-if="row.can_audit"><button v-for="action in auditActions(row)" :key="action.key" class="btn" :class="action.key === 'approve' ? 'btn-primary' : 'btn-secondary'" :disabled="busy.has(row.id)" @click="decision = { row, action: action.key, label: action.label, note: '' }">{{ busy.has(row.id) ? '处理中' : action.label }}</button></div>
        </article></div>
      </div>
      <nav class="pagination"><button class="btn btn-secondary" :disabled="loading || page <= 1" @click="load(page-1)">上一页</button><span>{{ page }} / {{ pages }}</span><button class="btn btn-secondary" :disabled="loading || page >= pages" @click="load(page+1)">下一页</button><select v-model.number="size" aria-label="每页条数" @change="load(1)"><option :value="5">每页5条</option><option :value="20">每页20条</option><option :value="50">每页50条</option></select></nav>
    </section>
    <Teleport to="body">
      <div v-if="preview" class="highlight-overlay" role="dialog" aria-modal="true" aria-label="亮点照片预览" @click.self="preview = ''"><button class="close" aria-label="关闭预览" @click="preview = ''">关闭</button><img class="full-photo" :src="preview" alt="亮点完整照片" /></div>
      <div v-if="decision" class="highlight-overlay" @click.self="decision = null"><form class="decision card-surface" role="dialog" aria-modal="true" aria-label="审核亮点" @submit.prevent="audit"><h3>{{ decision.label }} · {{ decision.row.display_id }}</h3><p>{{ decision.row.description }}</p><label>审核说明（选填）<textarea v-model="decision.note" maxlength="2000" rows="3" /></label><div class="actions"><button class="btn btn-secondary" type="button" @click="decision = null">取消</button><button class="btn btn-primary">确认{{ decision.label }}</button></div></form></div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
const labels = { pending: '待审核', approved: '已确认亮点', rejected: '审核未通过' }
const emptyFilters = () => ({ id: '', description: '', manager: '', inspector: '', region: '', station: '', table: '', status: '', date_from: '', date_to: '' })
const draft = ref(emptyFilters()), applied = ref(emptyFilters()), rows = ref([]), options = ref({}), optionsError = ref('')
const page = ref(1), size = ref(window.innerWidth <= 768 ? 5 : 20), total = ref(0), loading = ref(false), message = ref(''), preview = ref(''), decision = ref(null), busy = ref(new Set())
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(applied.value))
const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const textFields = [{ key: 'id', label: '亮点ID', placeholder: '例如 HL1（精确匹配）' }, { key: 'description', label: '亮点描述' }, { key: 'manager', label: '站点负责人' }, { key: 'inspector', label: '检查人员' }]
const optionFields = [{ key: 'region', label: '站点所属地', options: 'regions' }, { key: 'station', label: '站点名称', options: 'stations' }, { key: 'table', label: '检查表', options: 'tables' }]
const columns = [{key:'month',label:'检查月度'},{key:'time',label:'检查时间'},{key:'region',label:'站点所属地'},{key:'station',label:'站点名称'},{key:'station_manager',label:'站点负责人'},{key:'station_manager_phone',label:'站点负责人手机号'},{key:'inspector',label:'检查人员'},{key:'inspector_phone',label:'检查人员手机号'},{key:'inspection_table_name',label:'检查表'},{key:'description',label:'亮点描述'}]
const image = path => path ? `/storage/${String(path).replace(/^\//, '')}` : ''
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
const auditActions = row => row.audit_status === 'pending' ? [{key:'approve',label:'通过'},{key:'reject',label:'拒绝'}] : [{key:'reset',label:'重置审核'}]
let controller, sequence = 0
async function load(next = 1) {
  controller?.abort(); controller = new AbortController(); const current = ++sequence
  loading.value = true
  try {
    const { data } = await axios.get('/api/highlights', { params: { ...applied.value, page: next, page_size: size.value }, signal: controller.signal })
    if (current !== sequence) return
    rows.value = data.items; total.value = data.total; page.value = data.page
  } catch (e) { if (!axios.isCancel(e)) message.value = e.response?.data?.error || '亮点加载失败，请重新筛选。' }
  finally { if (current === sequence) loading.value = false }
}
async function loadOptions() {
  try { options.value = (await axios.get('/api/highlights/filter-options')).data; optionsError.value = '' }
  catch { optionsError.value = '筛选选项加载失败，请重试。' }
}
function apply() {
  if (draft.value.date_from && draft.value.date_to && draft.value.date_from > draft.value.date_to) { message.value = '开始日期不能晚于结束日期。'; return }
  applied.value = { ...draft.value }; message.value = ''; load(1)
}
async function audit() {
  const { row, action, note } = decision.value; decision.value = null; busy.value.add(row.id)
  try {
    const { data } = await axios.post(`/api/highlights/${row.id}/audit`, { action, note, expected_status: row.audit_status })
    const found = rows.value.find(item => item.id === row.id)
    if (found) { found.audit_status = data.audit_status; found.audit_note = note; found.audited_by_name = data.audited_by_name; found.audited_at = data.audited_at }
    if (applied.value.status && applied.value.status !== data.audit_status && found) { rows.value = rows.value.filter(item => item.id !== row.id); total.value-- }
    message.value = `${row.display_id}：${labels[data.audit_status]}`
  } catch (e) { message.value = e.response?.data?.error || '审核失败，请重试。' }
  finally { busy.value.delete(row.id) }
}
function keydown(event) { if (event.key === 'Escape') { preview.value = ''; decision.value = null } }
onMounted(() => { load(); loadOptions(); document.addEventListener('keydown', keydown) })
onBeforeUnmount(() => { controller?.abort(); sequence++; document.removeEventListener('keydown', keydown) })
</script>

<style scoped>
.highlights-page { display:grid; gap:20px; min-width:0; padding:24px; }
.highlights-page > * { min-width:0; }
.card-surface { background:#fff; border:1px solid #dfe8f1; border-radius:20px; box-shadow:0 8px 28px #23374d08; }
.page-header { padding:24px; background:linear-gradient(120deg,#fff,#f0f8fb); }.page-header h2 { margin:10px 0; }.page-desc { color:#61748a; line-height:1.7; margin-bottom:0; }
.eyebrow { color:#267a8e; font-size:13px; letter-spacing:2px; }
.filters,.results { padding:22px; border-radius:20px; }
.filter-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; }
label { display:grid; gap:8px; color:#64748b; font-size:13px; }
input,select,textarea { width:100%; min-height:42px; padding:9px 12px; border:1px solid #d7e1ec; border-radius:10px; background:white; color:#172b45; font:inherit; }
label.selected { color:#116e94; } label.selected input,label.selected select { border-color:#54a6c1; background:#f1faff; }
.actions,.pagination,.result-heading { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.filter-note { color:#61748a; font-size:13px; }.result-heading { justify-content:space-between; }.result-heading small { font-weight:400; color:#718198; }
.notice { padding:14px 20px; color:#126885; }.empty { text-align:center; padding:45px; color:#718198; }
.desktop-table { overflow:auto; }table { width:100%; border-collapse:collapse; font-size:14px; }th,td { padding:14px 12px; border-bottom:1px solid #e3ebf3; text-align:left; min-width:105px; }th { white-space:nowrap; background:#f2f7fb; }.description { min-width:250px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; }
.photo { border:0; border-radius:12px; padding:0; background:#f0f5fa; cursor:zoom-in; }.photo img { width:110px; height:82px; object-fit:contain; border-radius:12px; }
.status { display:inline-block; white-space:nowrap; border-radius:20px; padding:5px 10px; font-size:12px; background:#fff3d8; color:#916c12; }.status.approved { background:#e4f5ed; color:#176a46; }.status.rejected { background:#fceceb; color:#ad403e; }
.pagination { justify-content:center; margin-top:20px; }.pagination select { width:auto; }.mobile-cards { display:none; }
.highlight-overlay { position:fixed; inset:0; z-index:10000; background:#102038d9; display:flex; align-items:center; justify-content:center; padding:20px; }.full-photo { max-width:95vw; max-height:88dvh; object-fit:contain; }.close { position:absolute; right:20px; top:15px; border:0; padding:10px 18px; border-radius:10px; cursor:pointer; }.decision { background:white; border-radius:20px; padding:24px; max-width:550px; width:100%; max-height:90dvh; overflow:auto; }.decision p { white-space:pre-wrap; overflow-wrap:anywhere; }.decision .actions { margin-top:20px; }
@media(max-width:768px) { .filters,.results { padding:15px; }.filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }input,select,textarea { font-size:16px; }.desktop-table { display:none; }.mobile-cards { display:grid; gap:16px; }.highlight-card { border:1px solid #dce7f0; border-radius:16px; padding:16px; }.highlight-card header { display:flex; gap:8px; justify-content:space-between; flex-wrap:wrap; }.highlight-card .description { min-width:0; }.highlight-card .photo img { width:160px; height:120px; }dl { display:grid; grid-template-columns:110px 1fr; gap:8px; font-size:13px; }dt { color:#758397; }dd { margin:0; overflow-wrap:anywhere; }.result-heading span { display:none; } }
</style>
