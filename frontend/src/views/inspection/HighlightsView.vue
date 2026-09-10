<template>
  <div class="page-shell highlights-page">
    <header class="page-header card-surface">
      <div><div class="page-kicker">巡检系统</div><h2>亮点列表</h2></div>
    </header>
    <form class="card-surface filter-card" :class="{ 'mobile-expanded': showMobileFilters }" @submit.prevent="apply">
      <div class="filter-head">
        <div><div class="filter-kicker">筛选面板</div><h3>快速定位亮点记录</h3></div>
        <div class="filter-head-actions">
          <span v-if="activeFilterCount" class="active-filter-pill">已选 {{ activeFilterCount }} 项</span>
          <button type="button" class="btn btn-secondary mobile-filter-toggle" :aria-expanded="showMobileFilters" @click="showMobileFilters = !showMobileFilters">{{ showMobileFilters ? '收起筛选' : '展开筛选' }}</button>
        </div>
      </div>
      <FilterSummary :fields="filterSummaryFields" manual />
      <div class="filter-grid">
        <div class="filter-item" :data-filter-state="filterFieldState('id')"><label for="highlight-id">亮点ID</label><input id="highlight-id" v-model.trim="draft.id" placeholder="例如 HL1（精确匹配）" /></div>
        <div class="filter-item" :data-filter-state="filterFieldState('month')"><label for="highlight-month">检查月度</label><input id="highlight-month" v-model="draft.month" type="month" @change="draft.date_from = ''; draft.date_to = ''" /></div>
        <div class="filter-item" :data-filter-state="filterFieldState('dateRange')"><label>检查时间范围</label><DateRangePicker v-model:date-from="draft.date_from" v-model:date-to="draft.date_to" placeholder="选择检查时间范围" aria-label="选择亮点检查时间范围" @change="draft.month = ''" /></div>
        <div v-for="field in optionFields" :key="field.key" class="filter-item" :data-filter-state="filterFieldState(field.key)"><label>{{ field.label }}</label><InspectionFilterSelect v-model="draft[field.key]" :multiple="field.key !== 'manager'" :label="field.label" :options="options[field.options] || []" :loading="optionsLoading" :error="optionsError" @retry="loadOptions" /></div>
        <div class="filter-item" :data-filter-state="filterFieldState('description')"><label for="highlight-description">亮点描述</label><input id="highlight-description" v-model.trim="draft.description" placeholder="输入亮点描述" /></div>
        <div class="filter-item" :data-filter-state="filterFieldState('status')"><label for="highlight-status">亮点状态</label><select id="highlight-status" v-model="draft.status"><option value="">全部</option><option v-for="(label,key) in labels" :key="key" :value="key">{{ label }}</option></select></div>
      </div>
      <div class="filter-actions"><div class="filter-main-actions"><span v-if="dirty" class="filter-pending-hint">筛选条件已调整，点击开始筛选后生效</span><button type="button" class="btn btn-secondary" @click="draft = emptyFilters()">重置筛选</button><button class="btn btn-primary" :disabled="loading">{{ loading ? '筛选中...' : '开始筛选' }}</button></div></div>
      <p v-if="optionsError" role="alert">{{ optionsError }} <button type="button" class="btn btn-secondary" @click="loadOptions">重试</button></p>
    </form>
    <p v-if="message && !tableFullscreen" class="notice card-surface" role="status">{{ message }}</p>
    <section ref="tableCard" class="card-surface results" :class="{ 'fullscreen-table-card': tableFullscreen }" :aria-busy="loading">
      <div class="table-card-head"><div><div class="filter-kicker">亮点清单</div><h3>{{ tableFullscreen ? '全屏查看亮点' : '亮点明细' }}</h3></div>
        <div class="table-view-actions">
          <label v-if="tableFullscreen" class="zoom-control">缩放 {{ Math.round(tableZoom * 100) }}%<input v-model.number="tableZoom" type="range" min="0.2" max="1" step="0.02" /></label>
          <div ref="columnSettings" class="column-settings-wrap"><button class="btn btn-secondary" type="button" :aria-expanded="columnSettingsOpen" @click="columnSettingsOpen = !columnSettingsOpen">字段显示 {{ visibleDefinitions.length }}/{{ columnDefinitions.length }}</button>
            <div v-if="columnSettingsOpen" class="column-settings-panel card-surface"><header><strong>字段显示设置</strong><button class="btn btn-sm" aria-label="关闭字段设置" @click="columnSettingsOpen = false">×</button></header><p>隐藏暂时不看的字段，亮点数据不会受影响。</p><div class="actions"><button class="btn btn-primary btn-sm" @click="setColumns('all')">全部显示</button><button class="btn btn-secondary btn-sm" @click="setColumns('compact')">常用精简</button><button class="btn btn-secondary btn-sm" @click="setColumns('all')">恢复默认</button></div><div class="column-options"><label v-for="column in columnDefinitions" :key="column.key" :class="{ active: visible(column.key) }"><input type="checkbox" :checked="visible(column.key)" @change="toggleColumn(column.key)" />{{ column.label }}</label></div></div>
          </div><button class="btn btn-secondary" @click="toggleFullscreen">{{ tableFullscreen ? '退出全屏' : '全屏显示' }}</button>
        </div>
      </div>
      <div v-if="loading" class="table-empty-state" role="status"><div><div class="filter-kicker">筛选中</div><h3>正在查询亮点记录</h3><p>系统正在按已应用条件查询当前页，无需加载全部亮点。</p><div class="filter-query-progress" aria-hidden="true"><span></span></div></div></div>
      <div v-else-if="!rows.length" class="table-empty-state"><div><div class="filter-kicker">暂无记录</div><h3>当前没有符合条件的亮点记录</h3><p>可以调整筛选条件，然后点击“开始筛选”重新查询。</p></div></div>
      <div v-else class="table-content">
        <div class="desktop-table"><table :style="{ zoom: tableFullscreen ? tableZoom : 1 }"><thead><tr><th v-if="visible('id')">亮点ID</th><th v-for="column in columns" :key="column.key">{{ column.label }}</th><th v-if="visible('photo')">亮点照片</th><th v-if="visible('status')">亮点状态</th><th v-if="visible('audit')">审核</th><th v-if="canManage">操作</th></tr></thead>
          <tbody><tr v-for="row in rows" :key="row.id" :class="`audit-${row.audit_status}`"><td v-if="visible('id')"><strong>{{ row.display_id }}</strong></td><td v-for="column in columns" :key="column.key" :class="{ description: column.key === 'description' }">{{ row[column.key] || '—' }}</td>
            <td v-if="visible('photo')"><button class="photo" @click="preview = image(row.photo_path)"><img :src="image(row.photo_path)" loading="lazy" alt="亮点照片，点击放大" /></button></td>
            <td v-if="visible('status')"><span class="status" :class="row.audit_status">{{ labels[row.audit_status] }}</span></td>
            <td v-if="visible('audit')"><div class="actions audit-actions"><span v-if="busy.has(row.id)" class="audit-submitting-chip">后台提交中</span><template v-else><button v-for="action in row.can_audit ? auditActions(row) : []" :key="action.key" class="btn btn-sm" :class="auditButtonClass(action.key)" @click="decision = { row, action: action.key, label: action.label, note: '' }">{{ action.label }}</button><span v-if="!row.can_audit && row.audit_status === 'pending'">待审核</span></template></div><div v-if="row.audited_by_name" class="audit-meta">{{ row.audited_by_name }}<br />{{ formatTime(row.audited_at) }}</div><p v-if="row.audit_note">{{ row.audit_note }}</p></td>
<td v-if="canManage"><div class="table-actions"><button v-if="row.can_edit || row.can_change_inspector" class="btn btn-secondary btn-sm" :disabled="busy.has(row.id)" @click="openEdit(row)">{{ row.can_edit ? '编辑' : '调检查人' }}</button><button v-if="row.can_delete" class="btn btn-danger btn-sm" :disabled="busy.has(row.id)" @click="openDelete(row)">删除</button><span v-if="!row.can_edit && !row.can_delete && !row.can_change_inspector" class="audit-meta">{{ row.audit_status !== 'pending' ? '已审核，无操作权限' : '暂无可操作' }}</span></div></td>
          </tr></tbody></table></div>
        <div class="mobile-cards"><article v-for="row in rows" :key="row.id" class="highlight-card"><header><strong v-if="visible('id')">{{ row.display_id }}</strong><span v-if="visible('status')" class="status" :class="row.audit_status">{{ labels[row.audit_status] }}</span></header>
          <p v-if="visible('description')" class="description">{{ row.description }}</p><button v-if="visible('photo')" class="photo" @click="preview = image(row.photo_path)"><img :src="image(row.photo_path)" loading="lazy" alt="亮点照片，点击放大" /></button>
          <dl><template v-for="column in columns.filter(c => c.key !== 'description')" :key="column.key"><dt>{{ column.label }}</dt><dd>{{ row[column.key] || '—' }}</dd></template><template v-if="visible('audit')"><dt>审核人员</dt><dd>{{ row.audited_by_name || '待审核' }}</dd><dt>审核时间</dt><dd>{{ formatTime(row.audited_at) || '—' }}</dd><dt>审核说明</dt><dd>{{ row.audit_note || '—' }}</dd></template></dl>
          <div class="actions audit-actions" v-if="row.can_audit && visible('audit')"><span v-if="busy.has(row.id)" class="audit-submitting-chip">后台提交中</span><template v-else><button v-for="action in auditActions(row)" :key="action.key" class="btn" :class="auditButtonClass(action.key)" @click="decision = { row, action: action.key, label: action.label, note: '' }">{{ action.label }}</button></template></div>
          <div v-if="canManage" class="table-actions"><button v-if="row.can_edit || row.can_change_inspector" class="btn btn-secondary" :disabled="busy.has(row.id)" @click="openEdit(row)">{{ row.can_edit ? '编辑亮点' : '调整检查人' }}</button><button v-if="row.can_delete" class="btn btn-danger" :disabled="busy.has(row.id)" @click="openDelete(row)">删除</button></div>
        </article></div>
      </div>
      <nav class="pagination-bar" aria-label="亮点清单分页">
        <div class="pagination-summary">共 {{ total }} 条</div>
        <div class="pagination-controls">
          <div class="pagination-size-control"><label for="highlight-page-size">每页显示</label><select id="highlight-page-size" v-model.number="size" :disabled="loading" @change="load(1)"><option v-for="count in [5,10,20,50]" :key="count" :value="count">{{ count }}</option></select></div>
          <div class="pagination-nav-row"><button class="btn btn-secondary" :disabled="loading || page <= 1" @click="load(1)">首页</button><button class="btn btn-secondary" :disabled="loading || page <= 1" @click="load(page-1)">上一页</button></div>
          <div class="pagination-page-list"><template v-for="(value,index) in visiblePages" :key="index"><span v-if="value === '…'" class="pagination-ellipsis">…</span><button v-else class="pagination-page-btn" :class="{ active: value === page }" :aria-current="value === page ? 'page' : undefined" :disabled="loading" @click="load(value)">{{ value }}</button></template></div>
          <div class="pagination-nav-row"><button class="btn btn-secondary" :disabled="loading || page >= pages" @click="load(page+1)">下一页</button><button class="btn btn-secondary" :disabled="loading || page >= pages" @click="load(pages)">末页</button></div>
          <div class="pagination-jump"><span>跳至</span><input v-model="pageJump" type="number" min="1" :max="pages" :placeholder="`1-${pages}`" aria-label="跳转页码" @keyup.enter="jumpToPage" /><button class="btn btn-primary" :disabled="loading" @click="jumpToPage">跳转</button></div>
        </div>
      </nav>
      <div ref="overlayHost" class="fullscreen-overlay-host"></div>
    </section>
    <Teleport :to="tableFullscreen && overlayHost ? overlayHost : 'body'">
      <p v-if="message && tableFullscreen" class="notice fullscreen-notice" role="status" @click="message = ''">{{ message }}</p>
      <InspectionPhotoPreview v-if="preview" :url="preview" title="亮点照片" :style="{ zIndex: 12000 }" @close="preview = ''" />
      <div v-if="editing" class="highlight-overlay" @click.self="closeEdit"><form class="decision card-surface" role="dialog" aria-modal="true" aria-label="编辑亮点" @submit.prevent="saveEdit"><h3>{{ editing.row.can_edit ? '编辑亮点' : '调整检查人' }} · {{ editing.row.display_id }}</h3><label v-if="editing.row.can_edit">亮点描述<textarea v-model="editing.description" required maxlength="10000" rows="5" :disabled="saving" /></label><template v-if="editing.row.can_edit"><label>亮点照片（不选择则保留原照片）<input type="file" accept="image/*" :disabled="saving" @change="selectEditPhoto" /></label><button type="button" class="photo" @click="preview = editing.photoUrl || image(editing.row.photo_path)"><img :src="editing.photoUrl || image(editing.row.photo_path)" alt="当前亮点照片" /></button></template><label v-if="editing.row.can_change_inspector">检查人员<select v-model="editing.inspector" :disabled="saving || inspectorsLoading"><option value="">保留原检查人</option><option v-for="person in editInspectors" :key="person.id" :value="person.id">{{ person.name }}</option></select></label><p v-if="editError" role="alert">{{ editError }}</p><div class="actions"><button class="btn btn-secondary" type="button" :disabled="saving" @click="closeEdit">取消</button><button class="btn btn-primary" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button></div></form></div>
      <div v-if="deletion" class="highlight-overlay"><section class="decision card-surface" role="dialog" aria-modal="true" aria-label="确认删除亮点"><h3>删除 {{ deletion.display_id }}？</h3><p>此操作将删除该亮点及其关联审核记录，不能恢复。</p><p v-if="editError" role="alert">{{ editError }}</p><div class="actions"><button class="btn btn-secondary" :disabled="saving" @click="deletion = null">取消</button><button class="btn btn-danger" :disabled="saving" @click="removeHighlight">{{ saving ? '删除中…' : '确认删除' }}</button></div></section></div>
      <div v-if="decision" class="highlight-overlay" @click.self="decision = null"><form class="decision card-surface" role="dialog" aria-modal="true" aria-label="审核亮点" @submit.prevent="audit"><h3>{{ decision.label }} · {{ decision.row.display_id }}</h3><p>{{ decision.row.description }}</p><label>审核说明（选填）<textarea v-model="decision.note" maxlength="2000" rows="3" /></label><div class="actions"><button class="btn btn-secondary" type="button" @click="decision = null">取消</button><button class="btn" :class="auditButtonClass(decision.action)">确认{{ decision.label }}</button></div></form></div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
import FilterSummary from '@/components/FilterSummary.vue'
import DateRangePicker from '@/components/DateRangePicker.vue'
import InspectionFilterSelect from '@/components/InspectionFilterSelect.vue'
import InspectionPhotoPreview from '@/components/InspectionPhotoPreview.vue'
import { buildFilterSummary } from '@/utils/filterSummary'
const showMobileFilters = ref(false)
const tableCard = ref(null), overlayHost = ref(null), tableFullscreen = ref(false), tableZoom = ref(1)
const columnSettings = ref(null), columnSettingsOpen = ref(false), hiddenColumns = ref([]), canManage = ref(false)
const editing = ref(null), deletion = ref(null), saving = ref(false), editError = ref(''), editInspectors = ref([]), inspectorsLoading = ref(false)
const COLUMN_KEY = 'highlight-list-hidden-columns-v1'
try { const stored = JSON.parse(localStorage.getItem(COLUMN_KEY) || '[]'); if (Array.isArray(stored)) hiddenColumns.value = stored.filter(key => typeof key === 'string') } catch { /* Browser storage may be disabled. */ }
const visible = key => !hiddenColumns.value.includes(key)
const visibleDefinitions = computed(() => columnDefinitions.value.filter(column => visible(column.key)))
function persistColumns() { try { localStorage.setItem(COLUMN_KEY, JSON.stringify(hiddenColumns.value)) } catch { message.value = '浏览器不允许保存字段偏好，本次显示仍有效。' } }
function toggleColumn(key) {
  if (visible(key) && visibleDefinitions.value.length <= 1) { message.value = '至少保留一个字段显示。'; return }
  hiddenColumns.value = visible(key) ? [...hiddenColumns.value, key] : hiddenColumns.value.filter(value => value !== key)
  persistColumns()
}
function setColumns(mode) {
  hiddenColumns.value = mode === 'compact' ? columnDefinitions.value.filter(column => !['id','time','station','description','photo','status','audit'].includes(column.key)).map(column => column.key) : []
  persistColumns()
}
let previousOverflow = ''
async function exitFullscreen() {
  tableFullscreen.value = false; document.body.style.overflow = previousOverflow
  if (document.fullscreenElement === tableCard.value) { try { await document.exitFullscreen() } catch { /* Keep page fallback usable. */ } }
}
async function toggleFullscreen() {
  if (tableFullscreen.value) return exitFullscreen()
  previousOverflow = document.body.style.overflow; tableFullscreen.value = true; document.body.style.overflow = 'hidden'
  columnSettingsOpen.value = false
  await nextTick()
  try { await tableCard.value?.requestFullscreen?.() } catch { /* Mobile browsers can use fixed-position fullscreen. */ }
}
function fullscreenChanged() { if (!document.fullscreenElement && tableFullscreen.value) { tableFullscreen.value = false; document.body.style.overflow = previousOverflow } }
function outsideClick(event) { if (!columnSettings.value?.contains(event.target)) columnSettingsOpen.value = false }
function openDelete(row) { editError.value = ''; deletion.value = row }
async function openEdit(row) {
  editError.value = ''; editInspectors.value = []; editing.value = { row: { ...row }, description: row.description, inspector: '', photo: null, photoUrl: '' }
  if (!row.can_change_inspector) return
  inspectorsLoading.value = true
  try { const { data } = await axios.get(`/api/highlights/${row.id}/inspector-options`); if (editing.value?.row.id === row.id) editInspectors.value = data.items }
  catch (error) { if (editing.value?.row.id === row.id) editError.value = error.response?.data?.error || '检查人列表读取失败。' }
  finally { inspectorsLoading.value = false }
}
function closeEdit() { if (saving.value) return; if (editing.value?.photoUrl) URL.revokeObjectURL(editing.value.photoUrl); editing.value = null }
function selectEditPhoto(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) { editError.value = '请选择图片文件。'; return }
  if (editing.value.photoUrl) URL.revokeObjectURL(editing.value.photoUrl)
  editing.value.photo = file; editing.value.photoUrl = URL.createObjectURL(file)
}
async function saveEdit() {
  if (saving.value) return
  const entry = editing.value
  saving.value = true; editError.value = ''; busy.value.add(entry.row.id)
  try {
    const data = new FormData(); data.append('expected_revision',entry.row.revision)
    if (entry.row.can_edit) { data.append('description',entry.description); if (entry.photo) data.append('photo',entry.photo) }
    if (entry.inspector) data.append('target_inspector_id',entry.inspector)
    await axios.put(`/api/highlights/${entry.row.id}`,data)
    saving.value = false; closeEdit(); message.value = `${entry.row.display_id} 已保存。`; await load(page.value); loadOptions()
  } catch (error) { editError.value = error.response?.data?.error || '保存失败，请重试。' }
  finally { saving.value = false; busy.value.delete(entry.row.id) }
}
async function removeHighlight() {
  if (saving.value) return
  const row = deletion.value; saving.value = true; editError.value = ''; busy.value.add(row.id)
  try { await axios.delete(`/api/highlights/${row.id}`,{ data: { expected_revision: row.revision } }); deletion.value = null; message.value = `${row.display_id} 已删除。`; await load(page.value); loadOptions() }
  catch (error) { editError.value = error.response?.data?.error || '删除失败，请重试。' }
  finally { saving.value = false; busy.value.delete(row.id) }
}
const labels = { pending: '待审核', approved: '已确认亮点', rejected: '审核未通过' }
const emptyFilters = () => ({ id: '', month: '', description: '', manager: '', inspectors: [], region: [], station: [], table: [], status: '', date_from: '', date_to: '' })
const draft = ref(emptyFilters()), applied = ref(emptyFilters()), rows = ref([]), options = ref({}), optionsError = ref('')
const optionsLoading = ref(false)
const page = ref(1), size = ref(window.innerWidth <= 768 ? 5 : 20), total = ref(0), loading = ref(false), message = ref(''), preview = ref(''), decision = ref(null), busy = ref(new Set())
const dirty = computed(() => JSON.stringify(draft.value) !== JSON.stringify(applied.value))
const pages = computed(() => Math.max(1, Math.ceil(total.value / size.value)))
const pageJump = ref('')
const visiblePages = computed(() => {
  const selected = pages.value <= 7 ? Array.from({ length: pages.value }, (_, index) => index + 1)
    : [...new Set([1, page.value - 1, page.value, page.value + 1, pages.value])].filter(value => value >= 1 && value <= pages.value).sort((a,b) => a-b)
  return selected.flatMap((value, index) => index && value - selected[index - 1] > 1 ? ['…', value] : [value])
})
function jumpToPage() {
  const value = Number(pageJump.value)
  if (!loading.value && Number.isInteger(value) && value >= 1 && value <= pages.value) { load(value); pageJump.value = '' }
}
const optionFields = computed(() => [
  { key: 'region', label: '站点所属地', options: 'regions' }, { key: 'station', label: '站点名称', options: 'stations' },
  { key: 'manager', label: '站点负责人', options: 'managers' },
  ...(!options.value.hide_inspector_contact ? [{ key: 'inspectors', label: '检查人员', options: 'inspectors' }] : []),
  { key: 'table', label: '检查表', options: 'tables' }
])
const summaryValues = value => ({ ...value, dateFrom: value.date_from, dateTo: value.date_to, status: labels[value.status] || '' })
const filterSummaryFields = computed(() => buildFilterSummary(
  [['id', '亮点ID'], ['month', '检查月度'], ['dateRange', '检查时间范围'], ...optionFields.value.map(field => [field.key, field.label]), ['description', '亮点描述'], ['status', '亮点状态']],
  summaryValues(draft.value), summaryValues(applied.value)
))
const activeFilterCount = computed(() => filterSummaryFields.value.filter(field => field.value).length)
const filterFieldState = key => filterSummaryFields.value.find(field => field.key === key)?.state || 'empty'
const baseColumns = [{key:'month',label:'检查月度'},{key:'time',label:'检查时间'},{key:'region',label:'站点所属地'},{key:'station',label:'站点名称'},{key:'station_manager',label:'站点负责人'},{key:'station_manager_phone',label:'站点负责人手机号'},{key:'inspector',label:'检查人员'},{key:'inspector_phone',label:'检查人员手机号'},{key:'inspection_table_name',label:'检查表'},{key:'description',label:'亮点描述'}]
const columnDefinitions = computed(() => [{key:'id',label:'亮点ID'},...baseColumns.filter(column => !options.value.hide_inspector_contact || !['inspector','inspector_phone'].includes(column.key)),{key:'photo',label:'亮点照片'},{key:'status',label:'亮点状态'},{key:'audit',label:'审核'}])
const columns = computed(() => baseColumns.filter(column => visibleDefinitions.value.some(entry => entry.key === column.key)))
const image = path => {
  if (!path) return ''
  const value = String(path)
  return /^(https?:\/\/|blob:|data:|\/storage\/)/.test(value) ? value : `/storage/${value.replace(/^\//, '')}`
}
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
const auditActions = row => row.audit_status === 'pending' ? [{key:'approve',label:'通过'},{key:'reject',label:'否决'}] : [{key:'reset',label:'重新判定'}]
const auditButtonClass = action => ({ approve: 'btn-success', reject: 'btn-danger', reset: 'btn-secondary' }[action])
let controller, sequence = 0
async function load(next = 1) {
  controller?.abort(); controller = new AbortController(); const current = ++sequence
  loading.value = true
  try {
    const params = { ...applied.value, page: next, page_size: size.value }
    for (const key of ['region', 'station', 'table', 'inspectors']) params[key] = JSON.stringify(applied.value[key])
    const { data } = await axios.get('/api/highlights', { params, signal: controller.signal })
    if (current !== sequence) return
    rows.value = data.items; total.value = data.total; page.value = data.page; canManage.value = data.can_manage || data.items.some(row => row.can_edit || row.can_delete || row.can_change_inspector)
  } catch (e) { if (!axios.isCancel(e)) message.value = e.response?.data?.error || '亮点加载失败，请重新筛选。' }
  finally { if (current === sequence) loading.value = false }
}
async function loadOptions() {
  optionsLoading.value = true
  try { options.value = (await axios.get('/api/highlights/filter-options')).data; optionsError.value = '' }
  catch { optionsError.value = '筛选选项加载失败，请重试。' }
  finally { optionsLoading.value = false }
}
function apply() {
  if (draft.value.date_from && draft.value.date_to && draft.value.date_from > draft.value.date_to) { message.value = '开始日期不能晚于结束日期。'; return }
  applied.value = { ...draft.value }; message.value = ''; load(1)
}
async function audit() {
  const { row, action, note } = decision.value; decision.value = null; busy.value.add(row.id)
  try {
    const { data } = await axios.post(`/api/highlights/${row.id}/audit`, { action, note, expected_status: row.audit_status, expected_revision: row.revision })
    const found = rows.value.find(item => item.id === row.id)
    if (found) { Object.assign(found,data); found.audit_note = note }
    if (applied.value.status && applied.value.status !== data.audit_status && found) { rows.value = rows.value.filter(item => item.id !== row.id); total.value-- }
    message.value = `${row.display_id}：${labels[data.audit_status]}`
  } catch (e) { message.value = e.response?.data?.error || '审核失败，请重试。' }
  finally { busy.value.delete(row.id) }
}
function keydown(event) { if (event.key === 'Escape') { if (preview.value) preview.value = ''; else if (editing.value) closeEdit(); else if (deletion.value && !saving.value) deletion.value = null; else if (decision.value) decision.value = null; else if (columnSettingsOpen.value) columnSettingsOpen.value = false; else if (tableFullscreen.value) exitFullscreen() } }
onMounted(() => { load(); loadOptions(); document.addEventListener('keydown', keydown); document.addEventListener('fullscreenchange', fullscreenChanged); document.addEventListener('click',outsideClick) })
onBeforeUnmount(() => { controller?.abort(); sequence++; if (tableFullscreen.value) exitFullscreen(); if (editing.value?.photoUrl) URL.revokeObjectURL(editing.value.photoUrl); document.removeEventListener('keydown', keydown); document.removeEventListener('fullscreenchange', fullscreenChanged); document.removeEventListener('click',outsideClick) })
</script>

<style scoped>
.table-view-actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }.zoom-control { display:flex; align-items:center; white-space:nowrap; }.zoom-control input { width:120px; padding:0; }.column-settings-wrap { position:relative; }.column-settings-panel { position:absolute; right:0; top:48px; width:min(420px,calc(100vw - 48px)); padding:18px; z-index:30; background:white; max-height:65dvh; overflow:auto; }.column-settings-panel header { display:flex; align-items:center; justify-content:space-between; }.column-settings-panel p { font-size:12px; color:#64748b; }.column-options { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:14px; }.column-options label { display:flex; align-items:center; border:1px solid #dbe4ee; padding:8px; border-radius:9px; }.column-options label.active { background:#eff6ff; color:#1d4ed8; }.column-options input { width:16px; min-height:16px; accent-color:#2563eb; }
.table-actions { display:flex; flex-direction:column; align-items:center; gap:8px; min-width:100px; }.table-actions .btn { min-width:84px; }.desktop-table .audit-actions { flex-direction:column; gap:8px; min-width:100px; }.audit-actions .btn { min-width:84px; }.fullscreen-table-card { position:fixed; inset:0; z-index:3000; border-radius:0 !important; display:flex; flex-direction:column; box-sizing:border-box; background:white; height:100dvh; overflow:hidden; }.fullscreen-table-card .table-content { flex:1; min-height:0; display:flex; flex-direction:column; }.fullscreen-table-card .desktop-table { display:block; flex:1; max-height:none; min-height:0; }.fullscreen-table-card .mobile-cards { display:none; }.fullscreen-table-card .pagination-bar { flex-shrink:0; }.fullscreen-notice { position:fixed; top:18px; left:50%; transform:translateX(-50%); z-index:11000; background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; max-width:85vw; }.fullscreen-overlay-host { position:relative; z-index:4000; }.table-content { min-width:0; }
@media(max-width:768px) { .table-card-head { flex-direction:column; }.table-view-actions { width:100%; }.column-settings-panel { left:0; right:auto; }.fullscreen-table-card .pagination-controls { flex-direction:row; }.fullscreen-table-card .pagination-page-list,.fullscreen-table-card .pagination-jump { display:none; }.highlight-card .table-actions { margin-top:12px; } }
.highlights-page { display:flex; flex-direction:column; gap:20px; min-width:0; }
.highlights-page > * { min-width:0; }
.card-surface { background:rgba(255,255,255,.96); border:1px solid #dbe4ee; border-radius:22px; box-shadow:0 16px 36px rgba(15,23,42,.06); }
.page-header { padding:24px 28px; }
.page-header h2 { margin:0; font-size:34px; color:#0f172a; }
.page-kicker { display:inline-flex; padding:6px 12px; border-radius:999px; background:#eff6ff; color:#1d4ed8; font-size:12px; font-weight:700; margin-bottom:14px; }
.filter-card,.results { padding:20px; }
.filter-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px; margin-bottom:16px; }
.filter-kicker { display:inline-flex; margin-bottom:8px; padding:5px 10px; border-radius:999px; background:#ecfeff; color:#0f766e; font-size:12px; font-weight:900; }
.filter-head h3 { margin:0; color:#0f172a; font-size:18px; }
.filter-head-actions { display:flex; align-items:center; justify-content:flex-end; gap:10px; flex-wrap:wrap; }
.active-filter-pill { display:inline-flex; align-items:center; justify-content:center; min-height:32px; padding:0 11px; border-radius:999px; background:#eff6ff; color:#1d4ed8; font-size:12px; font-weight:900; }
.mobile-filter-toggle { display:none; }
.filter-grid { display:grid; grid-template-columns:repeat(4,minmax(220px,1fr)); gap:16px; }
.filter-item { display:flex; flex-direction:column; gap:8px; }
.filter-item label { font-size:14px; font-weight:700; color:#374151; }
.filter-item input,.filter-item select { height:42px; border-color:#d1d5db; padding:0 12px; font-size:14px; }
.filter-actions { margin-top:16px; display:flex; justify-content:flex-end; gap:12px; padding-top:14px; border-top:1px solid #eef2f7; }
.filter-main-actions { display:flex; align-items:center; justify-content:flex-end; gap:10px; flex-wrap:wrap; }
.filter-pending-hint { color:#a65d0b; font-size:12px; }
.btn { height:40px; padding:0 16px; border-radius:10px; border:1px solid #d1d5db; background:#fff; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; }
.btn-sm { height:34px; min-height:34px; padding:0 12px; border-radius:9px; font-size:13px; font-weight:700; }
.btn-primary { border-color:#1d4ed8; background:linear-gradient(135deg,#2563eb,#1d4ed8); color:#fff; font-weight:800; box-shadow:0 10px 22px rgba(37,99,235,.2); }
.btn-secondary { background:#f8fafc; color:#334155; border-color:#cbd5e1; font-weight:800; }
.btn-success { border-color:#bbf7d0; background:#f0fdf4; color:#15803d; font-weight:800; }.btn-success:hover:not(:disabled) { background:#dcfce7; }
.btn-danger { border-color:#fecaca; background:#fef2f2; color:#b91c1c; font-weight:800; }.btn-danger:hover:not(:disabled) { background:#fee2e2; }
.btn:disabled { cursor:not-allowed; opacity:.58; }
.audit-actions { justify-content:center; min-width:130px; }
.audit-meta { margin-top:8px; color:#64748b; font-size:12px; line-height:1.6; }
.audit-submitting-chip { display:inline-flex; padding:6px 10px; border-radius:999px; background:#eff6ff; color:#1d4ed8; font-size:12px; font-weight:800; }
label { display:grid; gap:8px; color:#64748b; font-size:13px; }
input,select,textarea { box-sizing:border-box; width:100%; min-height:42px; padding:9px 12px; border:1px solid #d7e1ec; border-radius:10px; background:white; color:#172b45; font:inherit; }
.actions,.pagination,.result-heading { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.filter-note { color:#61748a; font-size:13px; }.result-heading { justify-content:space-between; }.result-heading small { font-weight:400; color:#718198; }
.notice { padding:14px 20px; color:#126885; }.empty { text-align:center; padding:45px; color:#718198; }
.desktop-table { overflow:auto; max-height:60vh; border:1px solid #e5e7eb; border-radius:14px; }table { width:100%; border-collapse:collapse; font-size:14px; }th,td { padding:10px 12px; border:1px solid #e5e7eb; text-align:center; vertical-align:middle; color:#111827; min-width:105px; }th { white-space:nowrap; background:#f8fafc; font-weight:700; }.description { min-width:250px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.7; }
.audit-approved td { background:rgba(240,253,244,.86); }.audit-rejected td { background:rgba(254,242,242,.9); }.audit-approved:hover td { background:rgba(220,252,231,.9); }.audit-rejected:hover td { background:rgba(254,226,226,.92); }
.photo { border:0; border-radius:10px; padding:0; background:#f0f5fa; cursor:zoom-in; }.photo img { display:block; width:88px; height:66px; object-fit:contain; border-radius:10px; border:1px solid #cbd5e1; }
.status { display:inline-flex; align-items:center; justify-content:center; white-space:nowrap; border-radius:999px; padding:4px 10px; font-size:13px; font-weight:700; background:#f5f3ff; color:#7c3aed; }.status.approved { background:#f0fdf4; color:#16a34a; }.status.rejected { background:#fef2f2; color:#dc2626; }
.table-card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:14px; }
.table-card-head h3 { margin:0; color:#0f172a; font-size:18px; }
.table-empty-state { min-height:280px; border:1px solid #e5e7eb; border-radius:14px; background:linear-gradient(180deg,#fff,#f8fafc); display:flex; align-items:center; justify-content:center; padding:34px 18px; text-align:center; }
.table-empty-state h3 { color:#0f172a; }.table-empty-state p { color:#64748b; font-size:14px; line-height:1.7; }
.filter-query-progress { height:5px; max-width:260px; margin:20px auto 0; overflow:hidden; border-radius:99px; background:#dbeafe; }.filter-query-progress span { display:block; width:40%; height:100%; border-radius:inherit; background:#2563eb; animation:highlight-query 1.3s ease-in-out infinite; }
@keyframes highlight-query { from { transform:translateX(-100%); } to { transform:translateX(350%); } }
@media(prefers-reduced-motion:reduce) { .filter-query-progress span { animation:none; width:100%; } }
.pagination-bar { display:flex; justify-content:space-between; align-items:center; gap:16px; margin-top:16px; flex-wrap:wrap; }
.pagination-summary { color:#475569; font-size:14px; }
.pagination-controls { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
.pagination-size-control,.pagination-nav-row,.pagination-page-list,.pagination-jump { display:inline-flex; align-items:center; gap:8px; }
.pagination-size-control label,.pagination-jump span { color:#64748b; font-size:13px; font-weight:800; white-space:nowrap; }
.pagination-controls select,.pagination-jump input { width:auto; height:40px; border:1px solid #d1d5db; border-radius:10px; padding:0 10px; background:#fff; color:#0f172a; font-size:14px; }
.pagination-jump input { width:78px; text-align:center; }
.pagination-page-list { padding:4px; border:1px solid #e2e8f0; border-radius:14px; background:#f8fafc; }
.pagination-page-btn { width:34px; height:34px; border:0; border-radius:10px; background:transparent; color:#475569; font-size:13px; font-weight:900; cursor:pointer; }
.pagination-page-btn:hover { background:#e0edff; color:#1d4ed8; }.pagination-page-btn.active { background:#2563eb; color:#fff; box-shadow:0 8px 16px rgba(37,99,235,.22); }.pagination-ellipsis { min-width:28px; text-align:center; color:#94a3b8; }
.pagination { justify-content:center; margin-top:20px; }.pagination select { width:auto; }.mobile-cards { display:none; }
.highlight-overlay { position:fixed; inset:0; z-index:10000; background:#102038d9; display:flex; align-items:center; justify-content:center; padding:20px; }.full-photo { max-width:95vw; max-height:88dvh; object-fit:contain; }.close { position:absolute; right:20px; top:15px; border:0; padding:10px 18px; border-radius:10px; cursor:pointer; }.decision { background:white; border-radius:20px; padding:24px; max-width:550px; width:100%; max-height:90dvh; overflow:auto; }.decision p { white-space:pre-wrap; overflow-wrap:anywhere; }.decision .actions { margin-top:20px; }
@media(max-width:768px) { .filters,.results { padding:15px; }.filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }input,select,textarea { font-size:16px; }.desktop-table { display:none; }.mobile-cards { display:grid; gap:16px; }.highlight-card { border:1px solid #dce7f0; border-radius:16px; padding:16px; }.highlight-card header { display:flex; gap:8px; justify-content:space-between; flex-wrap:wrap; }.highlight-card .description { min-width:0; }.highlight-card .photo img { width:160px; height:120px; }dl { display:grid; grid-template-columns:110px 1fr; gap:8px; font-size:13px; }dt { color:#758397; }dd { margin:0; overflow-wrap:anywhere; }.result-heading span { display:none; } }
@media(max-width:1200px) { .filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media(max-width:768px) {
  .highlights-page { gap:14px; }
  .page-header { padding:18px 16px; }
  .page-header h2 { font-size:28px; }
  .page-kicker { margin-bottom:10px; }
  .filter-card { padding:14px; border-radius:20px; }
  .filter-head { align-items:center; margin-bottom:0; }
  .filter-card.mobile-expanded .filter-head { margin-bottom:14px; }
  .filter-head h3 { font-size:17px; }
  .filter-head-actions { align-items:flex-end; flex-direction:column; gap:8px; }
  .mobile-filter-toggle { display:inline-flex; min-height:38px; }
  .filter-card:not(.mobile-expanded) .filter-grid,.filter-card:not(.mobile-expanded) .filter-actions { display:none; }
  .filter-grid { grid-template-columns:minmax(0,1fr); gap:14px; }
  .filter-item label { font-size:13px; }
  .filter-item input,.filter-item select { height:46px; font-size:16px; }
  .filter-actions,.filter-main-actions { flex-direction:column; align-items:stretch; width:100%; }
  .filter-actions { padding-top:0; border-top:0; }
  .filter-main-actions .btn { width:100%; }
  .pagination-bar,.pagination-controls { flex-direction:column; align-items:stretch; }
  .pagination-nav-row .btn { flex:1; }
  .pagination-page-list { justify-content:center; flex-wrap:wrap; }
  .pagination-controls select,.pagination-jump input { font-size:16px; }
  .table-empty-state { min-height:220px; }
}
</style>
