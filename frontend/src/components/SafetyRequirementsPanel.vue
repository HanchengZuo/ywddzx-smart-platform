<template>
  <article class="requirements-panel" aria-label="报告规范要求维护">
    <header>
      <div>
        <small>02 · 规范要求</small>
        <h3>检查规范与报告要求</h3>
        <p>
          将检查规范整理为可直接用于报告的规范要求，不使用评分说明代替。所有报告配置用户均可查看和维护。
        </p>
      </div>
      <button :aria-expanded="expanded" :disabled="working || busy" @click="toggle">
        {{ expanded ? '收起规范要求' : '查看与维护规范要求' }}
      </button>
    </header>
    <section v-if="expanded" class="requirements-content">
      <p v-if="error" class="requirements-error" role="alert">{{ error }}</p>
      <p v-if="notice" class="requirements-notice" role="status">{{ notice }}</p>
      <p v-if="loading" role="status">正在读取规范目录和已保存要求，不调用 AI…</p>
      <template v-else-if="catalog">
        <div class="requirements-toolbar">
          <label
            >检查方式<select v-model="mode">
              <option value="">现场与视频</option>
              <option value="onsite">现场检查</option>
              <option value="video">视频检查</option>
            </select></label
          >
          <label
            >状态<select v-model="status">
              <option value="">所有状态</option>
              <option value="missing">待补充</option>
              <option value="stale">规范有更新</option>
              <option value="ready">AI 已就绪</option>
              <option value="manual">人工维护</option>
            </select></label
          >
          <label class="requirements-search"
            >搜索规范<input v-model="keyword" type="search" placeholder="规范ID、检查内容、要求"
          /></label>
        </div>
        <div class="requirements-actions">
          <span
            >{{ catalog.standards.length }} 条规范 · {{ pendingCount }} 条待补充或更新 ·
            {{ changes.length }} 条未保存</span
          >
          <button :disabled="working || busy || !!changes.length" @click="load">重新读取</button>
          <button
            :disabled="
              !canGenerate ||
              !catalog.can_generate ||
              working ||
              busy ||
              !!changes.length ||
              !pendingCount
            "
            @click="generate"
          >
            {{ generating ? '正在生成规范要求…' : 'AI补齐缺失或过期要求' }}
          </button>
          <button
            class="requirements-primary"
            :disabled="working || busy || !changes.length"
            @click="save"
          >
            {{ saving ? '正在保存…' : `保存修改${changes.length ? `（${changes.length}）` : ''}` }}
          </button>
        </div>
        <p class="requirements-help">
          仅明确点击生成按钮才调用
          AI，且只处理缺失或过期条目。修改后请先保存；人工保存使用各条规范的版本校验，避免覆盖其他用户的更新。
        </p>
        <p v-if="!canGenerate || !catalog.can_generate" class="requirements-help">
          当前账号无生成 AI 报告权限，仍可查看、编辑和保存规范要求。
        </p>
        <p v-if="!visibleStandards.length" class="requirements-empty">没有符合条件的规范。</p>
        <article v-for="row in visibleStandards" :key="row.key" class="requirement-row">
          <header>
            <div>
              <strong
                >{{ row.mode === 'video' ? '视频' : '现场' }} ·
                {{ row.external_standard_id || row.key }}</strong
              >
              <h4>
                {{
                  row.fields?.['检查内容'] ||
                  row.fields?.['检查项'] ||
                  row.fields?.['检查主题'] ||
                  '检查规范'
                }}
              </h4>
            </div>
            <span class="requirement-status" :class="row.status"
              >{{ statusLabels[row.status] || '待补充'
              }}{{ isEdited(row) ? ' · 未保存' : '' }}</span
            >
          </header>
          <details>
            <summary>查看原始规范字段</summary>
            <dl>
              <div v-for="(value, label) in row.fields" :key="label">
                <dt>{{ label }}</dt>
                <dd>{{ value || '未维护' }}</dd>
              </div>
            </dl>
          </details>
          <label
            >报告规范要求<textarea
              v-model="draft[row.key]"
              :disabled="working || busy"
              rows="3"
              placeholder="请维护应遵守的规范要求，而非扣分标准或评分说明"
            ></textarea>
          </label>
          <details v-if="row.ai_requirement">
            <summary>查看 AI 原建议</summary>
            <p>{{ row.ai_requirement }}</p>
            <button
              :disabled="working || busy || draft[row.key] === row.ai_requirement"
              @click="draft[row.key] = row.ai_requirement"
            >
              采用该建议（待保存）
            </button>
          </details>
          <footer>
            <span>{{
              row.updated_by_name
                ? `最近保存：${row.updated_by_name} · ${safetyUpdatedAt(row.updated_at)}`
                : '尚无人工保存记录'
            }}</span
            ><button
              v-if="isEdited(row)"
              :disabled="working || busy"
              @click="draft[row.key] = row.requirement || ''"
            >
              撤销本条修改
            </button>
          </footer>
        </article>
      </template>
      <button v-else-if="!loading" :disabled="working || busy" @click="load">
        重新读取规范要求
      </button>
    </section>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
import { safetyRequirementChanges, safetyUpdatedAt } from '@/utils/safetyReportConfig'
const props = defineProps({ canGenerate: Boolean, busy: Boolean })
const emit = defineEmits(['saved'])
const expanded = ref(false),
  catalog = ref(null),
  draft = ref({}),
  loading = ref(false),
  saving = ref(false),
  generating = ref(false),
  error = ref(''),
  notice = ref(''),
  mode = ref(''),
  status = ref(''),
  keyword = ref('')
let sequence = 0,
  controller,
  alive = true
const endpoint = '/api/inspection-reports/safety-requirements'
const statusLabels = {
  ready: 'AI 已就绪',
  manual: '人工维护',
  stale: '规范有更新，待核对',
  missing: '待补充',
}
const working = computed(() => loading.value || saving.value || generating.value)
const changes = computed(() => safetyRequirementChanges(catalog.value?.standards, draft.value))
const pendingCount = computed(
  () =>
    (catalog.value?.standards || []).filter((row) => ['missing', 'stale'].includes(row.status))
      .length,
)
const visibleStandards = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  return (catalog.value?.standards || []).filter(
    (row) =>
      (!mode.value || row.mode === mode.value) &&
      (!status.value || row.status === status.value) &&
      (!query ||
        [row.external_standard_id, ...Object.values(row.fields || {}), draft.value[row.key]].some(
          (value) =>
            String(value || '')
              .toLowerCase()
              .includes(query),
        )),
  )
})
const isEdited = (row) => draft.value[row.key] !== (row.requirement || '')
function adopt(value) {
  if (value.success === false) throw new Error(value.error || '规范要求处理失败。')
  catalog.value = value
  draft.value = Object.fromEntries(
    (value.standards || []).map((row) => [row.key, row.requirement || '']),
  )
}
function toggle() {
  if (working.value) return
  expanded.value = !expanded.value
  if (expanded.value && !catalog.value) load()
}
async function load() {
  if (working.value || props.busy || changes.value.length) return
  const id = ++sequence
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get(endpoint, { signal: controller.signal })
    if (id === sequence && alive) adopt(response.data)
  } catch (err) {
    if (id === sequence && alive && !axios.isCancel(err))
      error.value = err.response?.data?.error || err.message || '规范要求读取失败。'
  } finally {
    if (id === sequence && alive) loading.value = false
  }
}
async function save() {
  if (working.value || props.busy || !changes.value.length) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const response = await axios.put(endpoint, {
      catalog_signature: catalog.value.catalog_signature,
      changes: changes.value,
    })
    if (!alive) return
    adopt(response.data)
    notice.value = '规范要求已保存，报告配置中的规范文本已同步刷新。重新生成报告后应用。'
    emit('saved')
  } catch (err) {
    if (alive)
      error.value = err.response?.data?.error || err.message || '保存失败，已保留未保存修改。'
  } finally {
    if (alive) saving.value = false
  }
}
async function generate() {
  if (
    !props.canGenerate ||
    !catalog.value?.can_generate ||
    working.value ||
    props.busy ||
    changes.value.length ||
    !pendingCount.value
  )
    return
  generating.value = true
  error.value = ''
  notice.value = ''
  try {
    const response = await axios.post(
      endpoint,
      { catalog_signature: catalog.value.catalog_signature },
      { timeout: 300000 },
    )
    if (!alive) return
    adopt(response.data)
    notice.value = '缺失或过期规范要求已处理，报告配置已刷新；人工修改条目保持不变。'
    emit('saved')
  } catch (err) {
    if (alive)
      error.value = err.response?.data?.error || err.message || '生成未完成，原保存内容不变。'
  } finally {
    if (alive) generating.value = false
  }
}
onBeforeUnmount(() => {
  alive = false
  sequence++
  controller?.abort()
})
</script>

<style scoped>
.requirements-panel {
  --ink: #294b65;
  --line: #c4d7e5;
  color: var(--ink);
  border: 1px solid var(--line);
  border-top: 3px solid #438b82;
  border-radius: 14px;
  margin-top: 16px;
  background: linear-gradient(120deg, #f2f8f7, #fff);
  padding: 22px;
  font-size: 15px;
  line-height: 1.7;
}
.requirements-panel > header,
.requirement-row > header {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
}
.requirements-panel h3 {
  margin: 6px 0 10px;
  font-size: 20px;
  color: #173951;
}
.requirements-panel small {
  font-size: 13px;
  font-weight: 700;
}
.requirements-panel p {
  margin: 8px 0 14px;
}
.requirements-panel button {
  border: 1px solid #acc6d7;
  border-radius: 8px;
  padding: 10px 14px;
  background: white;
  color: #225373;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.requirements-panel > header > button {
  flex-shrink: 0;
}
.requirements-panel button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.requirements-panel :focus-visible {
  outline: 3px solid #64a6d1;
  outline-offset: 2px;
}
.requirements-content {
  border-top: 1px solid var(--line);
  margin-top: 18px;
  padding-top: 18px;
}
.requirements-toolbar {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.requirements-toolbar > label {
  min-width: 145px;
}
.requirements-search {
  flex: 1;
}
.requirements-panel input,
.requirements-panel select,
.requirements-panel textarea {
  box-sizing: border-box;
  width: 100%;
  display: block;
  margin: 6px 0 12px;
  padding: 10px;
  border: 1px solid #adc6d6;
  background: white;
  color: #233e55;
  border-radius: 8px;
  font: inherit;
}
.requirements-panel textarea {
  resize: vertical;
  min-height: 100px;
}
.requirements-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 10px 0;
}
.requirements-actions > span {
  flex: 1 1 100%;
}
.requirements-panel .requirements-primary {
  background: #17637e;
  color: white;
  border-color: #17637e;
}
.requirements-help,
.requirement-row footer {
  font-size: 14px;
  color: #547184;
}
.requirement-row {
  background: white;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 18px;
  margin-top: 16px;
}
.requirement-row h4 {
  margin: 6px 0;
  font-size: 17px;
  overflow-wrap: anywhere;
}
.requirement-status {
  padding: 4px 9px;
  background: #e4f1ee;
  color: #22695e;
  border-radius: 6px;
  font-size: 14px;
}
.requirement-status.stale,
.requirement-status.missing {
  background: #fff1dc;
  color: #88601a;
}
.requirement-row details {
  padding: 10px 0;
}
.requirement-row summary {
  cursor: pointer;
  color: #366b80;
}
.requirement-row dl {
  margin: 10px 0;
  background: #f4f8fb;
  padding: 12px;
  border-radius: 8px;
}
.requirement-row dl > div {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 12px;
  padding: 6px 0;
}
.requirement-row dd {
  margin: 0;
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.requirement-row details p {
  white-space: pre-line;
}
.requirement-row > label {
  display: block;
  margin-top: 10px;
  font-weight: 600;
}
.requirement-row footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}
.requirements-error,
.requirements-notice {
  padding: 12px;
  border-radius: 8px;
  background: #fff1ef;
  color: #a1332a;
}
.requirements-notice {
  background: #e6f3ef;
  color: #246957;
}
.requirements-empty {
  padding: 20px;
  text-align: center;
  color: #647f90;
}
@media (max-width: 700px) {
  .requirements-panel {
    padding: 16px;
  }
  .requirements-panel > header,
  .requirement-row > header {
    align-items: flex-start;
    flex-direction: column;
  }
  .requirements-toolbar > label {
    flex: 1 1 100%;
  }
  .requirements-actions button {
    flex: 1 1 100%;
  }
  .requirement-row dl > div {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
