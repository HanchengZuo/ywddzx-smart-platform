<template>
  <article class="requirements-panel" aria-label="报告规范要求维护">
    <small>03 · 规范要求</small>
    <h3>检查规范与报告要求</h3>
    <p>提前准备各条规范对应的报告要求，支持 AI 整理和人工修订；规范不变时直接复用历史内容。</p>
    <button aria-haspopup="dialog" :disabled="working || busy" @click="toggle">
      查看与维护规范要求
    </button>
    <small v-if="changes.length" class="requirements-unsaved"
      >{{ changes.length }} 条修改尚未保存</small
    >
    <Teleport to="body">
      <div
        v-if="expanded"
        class="requirements-overlay"
        @click.self="close"
        @keydown.esc.stop="close"
      >
        <section
          ref="dialog"
          class="requirements-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="requirements-title"
          tabindex="-1"
          @keydown.tab="trapFocus"
        >
          <header class="requirements-modal-header">
            <div>
              <small>安全质量检查报告 · 规范要求库</small>
              <h2 id="requirements-title">检查规范与报告要求</h2>
              <p>原始规范为依据，AI 建议与人工修订分开保留。</p>
            </div>
            <button
              class="requirements-close"
              :disabled="saving || generating"
              aria-label="关闭规范要求"
              @click="close"
            >
              ×
            </button>
          </header>
          <section class="requirements-content">
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
                  >搜索规范<input
                    v-model="keyword"
                    type="search"
                    placeholder="规范ID、检查内容、要求"
                /></label>
              </div>
              <div class="requirements-actions">
                <span
                  >{{ catalog.standards.length }} 条规范 · {{ pendingCount }} 条待补充或更新 ·
                  {{ changes.length }} 条未保存</span
                >
                <button :disabled="working || busy || !!changes.length" @click="load">
                  重新读取
                </button>
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
              </div>
              <p class="requirements-help">
                AI
                只补齐缺失或过期条目，已保存内容直接复用。人工修改先保存，版本校验防止覆盖他人更新。
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
                  >报告规范要求<span class="requirement-length"
                    >{{ (draft[row.key] || '').length }} / 240</span
                  ><textarea
                    v-model="draft[row.key]"
                    :disabled="working || busy"
                    maxlength="240"
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
          <footer class="requirements-modal-footer">
            <div>
              <strong>{{
                changes.length ? `${changes.length} 条修改待保存` : '当前内容已与保存记录同步'
              }}</strong>
              <span>保存不调用 AI；重新生成报告后应用。关闭此弹窗会保留尚未保存的编辑。</span>
            </div>
            <button :disabled="saving || generating" @click="close">关闭</button>
            <button
              class="requirements-primary"
              :disabled="working || busy || !changes.length"
              @click="save"
            >
              {{
                saving ? '正在保存…' : `保存修改${changes.length ? `（${changes.length}）` : ''}`
              }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </article>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
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
const dialog = ref(null)
let sequence = 0,
  controller,
  alive = true,
  previousFocus,
  bodyOverflow
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
async function toggle() {
  if (working.value) return
  if (expanded.value) return close()
  previousFocus = document.activeElement
  if (document.body?.style) {
    bodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  expanded.value = true
  document.addEventListener?.('keydown', onDocumentKeydown)
  if (!catalog.value) load()
  await nextTick()
  dialog.value?.focus()
}
function restoreBody() {
  if (bodyOverflow !== undefined && document.body?.style)
    document.body.style.overflow = bodyOverflow
  bodyOverflow = undefined
}
function close() {
  if (saving.value || generating.value) return
  if (loading.value) {
    sequence++
    controller?.abort()
    loading.value = false
  }
  expanded.value = false
  document.removeEventListener?.('keydown', onDocumentKeydown)
  restoreBody()
  previousFocus?.focus()
}
function onDocumentKeydown(event) {
  if (expanded.value && event.key === 'Escape') {
    event.preventDefault()
    close()
  }
}
function trapFocus(event) {
  const nodes = [
    ...dialog.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
    ),
  ]
  if (!nodes.length) {
    event.preventDefault()
    dialog.value?.focus()
    return
  }
  if (
    document.activeElement === (event.shiftKey ? nodes[0] : nodes.at(-1)) ||
    document.activeElement === dialog.value
  ) {
    event.preventDefault()
    ;(event.shiftKey ? nodes.at(-1) : nodes[0])?.focus()
  }
}
async function load() {
  if (working.value || props.busy || changes.value.length) return
  const id = ++sequence
  controller?.abort()
  document.removeEventListener?.('keydown', onDocumentKeydown)
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
    if (alive) {
      const message = err.response?.data?.error || err.message || '生成未完成，已保存条目仍可复用。'
      const before = catalog.value?.library_signature
      // Completed batches survive a later failure. Reflect those saved rows
      // without retrying AI or discarding edits (generation requires no edits).
      try {
        const response = await axios.get(endpoint)
        if (alive) {
          adopt(response.data)
          if (before && before !== response.data.library_signature) emit('saved')
        }
      } catch {
        // Preserve the original generation error when the follow-up read fails.
      }
      if (alive) error.value = message
    }
  } finally {
    if (alive) generating.value = false
  }
}
onBeforeUnmount(() => {
  alive = false
  sequence++
  controller?.abort()
  restoreBody()
})
</script>

<style scoped>
.requirements-panel {
  --ink: #294b65;
  --line: #c4d7e5;
  color: var(--ink);
  margin: 0;
  border: 0;
  border-radius: 0;
  background: #fbfdfc;
  padding: 25px 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  font-size: 15px;
  line-height: 1.7;
}
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
  line-height: 1.4;
  letter-spacing: 0.7px;
  padding: 4px 9px;
  border-radius: 5px;
  color: #22675d;
  background: #e5f1ee;
  margin-bottom: 10px;
}
.requirements-panel p {
  margin: 6px 0 20px;
  color: #496579;
}
.requirements-panel > button,
.requirements-modal button {
  border: 1px solid #9dbbd0;
  border-radius: 8px;
  padding: 10px 14px;
  background: white;
  color: #225373;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.requirements-panel > button {
  margin-top: auto;
  min-height: 44px;
  line-height: 1.5;
  font-size: 15px;
  box-sizing: border-box;
  box-shadow: 0 2px 5px #17395108;
}
.requirements-panel > button:hover:not(:disabled) {
  background: #edf5f9;
  border-color: #4c809e;
}
.requirements-panel > button:disabled,
.requirements-modal button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.requirements-panel :focus-visible,
.requirements-modal :focus-visible {
  outline: 3px solid #64a6d1;
  outline-offset: 2px;
}
.requirements-content {
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 24px 28px;
  min-height: 0;
}
.requirements-overlay {
  position: fixed;
  inset: 0;
  z-index: 4400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #102a47a8;
}
.requirements-modal {
  --ink: #294b65;
  --line: #c4d7e5;
  display: flex;
  flex-direction: column;
  width: min(1180px, 96vw);
  max-height: 90dvh;
  border-radius: 18px;
  box-shadow: 0 24px 90px #061d3d66;
  background: #fff;
  color: var(--ink);
  overflow: hidden;
  font-size: 15px;
  line-height: 1.7;
}
.requirements-modal-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: center;
  flex-shrink: 0;
  padding: 20px 28px;
  border-bottom: 1px solid var(--line);
  background: #edf5f4;
}
.requirements-modal-header h2 {
  margin: 4px 0;
  font-size: 23px;
  color: #173951;
}
.requirements-modal-header small {
  font-size: 13px;
  color: #517378;
}
.requirements-modal-header p {
  margin: 0;
  color: #496579;
}
.requirements-modal .requirements-close {
  padding: 0;
  width: 38px;
  height: 38px;
  flex-shrink: 0;
  border-radius: 10px;
  font-size: 26px;
  line-height: 1;
}
.requirements-modal-footer {
  flex-shrink: 0;
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 16px 28px;
  border-top: 1px solid var(--line);
  background: #f8fbfc;
}
.requirements-modal-footer > div {
  flex: 1;
  font-size: 14px;
}
.requirements-modal-footer span {
  display: block;
  font-size: 13px;
  color: #526e81;
}
.requirements-panel .requirements-unsaved {
  margin: 12px 0 0;
  background: #fff1dc;
  color: #805613;
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
.requirements-modal input,
.requirements-modal select,
.requirements-modal textarea {
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
.requirements-modal textarea {
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
.requirements-modal .requirements-primary {
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
.requirement-length {
  float: right;
  color: #648094;
  font-size: 13px;
  font-weight: 400;
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
    padding: 22px;
  }
  .requirement-row > header {
    align-items: flex-start;
    flex-direction: column;
  }
  .requirements-toolbar > label {
    flex: 1 1 calc(50% - 7px);
    min-width: 0;
  }
  .requirements-toolbar > .requirements-search {
    flex-basis: 100%;
  }
  .requirements-actions button {
    flex: 1 1 100%;
  }
  .requirement-row dl > div {
    grid-template-columns: 1fr;
    gap: 2px;
  }
  .requirements-overlay {
    padding: 8px;
  }
  .requirements-modal {
    max-height: 96dvh;
    width: 100%;
    border-radius: 14px;
  }
  .requirements-modal-header {
    padding: 16px;
    gap: 12px;
  }
  .requirements-modal-header h2 {
    font-size: 20px;
  }
  .requirements-modal-header p {
    font-size: 13px;
  }
  .requirements-content {
    padding: 16px;
  }
  .requirements-modal-footer {
    padding: 12px 16px;
    gap: 8px;
    flex-wrap: wrap;
  }
  .requirements-modal-footer > div {
    flex-basis: 100%;
  }
}
</style>
