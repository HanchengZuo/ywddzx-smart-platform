<template>
  <article class="phrases-tool">
    <small>06 · 统计短语</small>
    <h3>检查内容与评分项短语</h3>
    <p>现场沿用检查内容短语，视频提炼评分项短语；人工修订优先，统一用于重点问题分析。</p>
    <button :disabled="busy" aria-haspopup="dialog" @click="open">查看与维护统计短语</button>
    <Teleport to="body">
      <div v-if="expanded" class="phrases-overlay" @click.self="close" @keydown.esc.stop="close">
        <section
          ref="dialog"
          class="phrases-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="phrases-title"
          tabindex="-1"
          @keydown.tab="trapFocus"
        >
          <header>
            <div>
              <small>安全质量检查报告 · 全局共享配置</small>
              <h2 id="phrases-title">统计短语库</h2>
              <p>调整统计名称，不修改原始规范，也不改变问题归属。</p>
            </div>
            <button
              class="phrases-close"
              :disabled="saving || generating"
              aria-label="关闭统计短语"
              @click="close"
            >
              ×
            </button>
          </header>
          <div v-if="loading" class="phrases-state" role="status">
            正在读取规范来源与已保存短语…
          </div>
          <div v-else class="phrases-layout">
            <nav aria-label="统计短语检查方式">
              <button
                v-for="item in modes"
                :key="item.key"
                :class="{ selected: mode === item.key }"
                :aria-pressed="mode === item.key"
                @click="mode = item.key"
              >
                <b>{{ item.label }}</b
                ><span>{{ item.field }}</span>
                <small>{{ rows.filter((row) => row.mode === item.key).length }} 类来源</small>
              </button>
              <p>相同源字段共用一个短语；相同短语会在图表中合并计数。</p>
              <p>人工保存不调用 AI。保存后重新生成报告，才会应用到成稿。</p>
            </nav>
            <div class="phrases-main">
              <div class="phrases-toolbar">
                <label
                  >搜索来源或短语<input
                    v-model="keyword"
                    type="search"
                    placeholder="规范 ID、原文或统计短语"
                /></label>
                <button :disabled="working || busy" @click="reload">
                  {{ changeCount ? '放弃修改并重读' : '重新读取' }}
                </button>
                <button
                  v-if="mode === 'video'"
                  class="phrases-primary"
                  :disabled="
                    working ||
                    busy ||
                    !canGenerate ||
                    !data?.can_generate ||
                    !pending ||
                    !!changeCount
                  "
                  @click="generate"
                >
                  {{ generating ? '正在生成…' : `AI 补齐短语（${pending}）` }}
                </button>
              </div>
              <p v-if="error" class="phrases-error" role="alert">{{ error }}</p>
              <p v-if="notice" class="phrases-notice" role="status">{{ notice }}</p>
              <div class="phrases-list-summary">
                {{ visible.length }} 类来源 · {{ changeCount }} 条待保存
                <span>{{
                  mode === 'onsite' ? '检查内容 → 统计名称' : '评分项 → AI 短语 / 人工修订'
                }}</span>
              </div>
              <div class="phrases-rows">
                <article
                  v-for="row in visible"
                  :key="row.key"
                  :class="{ edited: draft[row.key] !== row.phrase }"
                >
                  <div class="phrases-source">
                    <div>
                      <b>规范 {{ row.standard_ids.join('、') }}</b
                      ><span :class="['phrases-status', row.status]">{{
                        statusLabels[row.status]
                      }}</span>
                    </div>
                    <p>{{ row.source || '该规范未填写检查内容，沿用“其他”统计名称。' }}</p>
                  </div>
                  <label class="phrases-edit"
                    >报告统计短语
                    <input
                      v-model="draft[row.key]"
                      maxlength="30"
                      :aria-label="`规范${row.standard_ids.join('、')}统计短语`"
                      :disabled="saving || generating"
                      placeholder="输入简短、明确的统计名称"
                    />
                    <small v-if="row.ai_phrase">AI 原始建议：{{ row.ai_phrase }}</small>
                    <small v-else>{{
                      mode === 'onsite'
                        ? '沿用既有短语，可直接编辑'
                        : '可使用 AI 补齐，也可直接填写'
                    }}</small>
                  </label>
                </article>
                <p v-if="!visible.length" class="phrases-state">没有匹配的规范来源。</p>
              </div>
            </div>
          </div>
          <footer>
            <span>{{ savedLabel }}<small>修改全局共享；PPT 预览与导出使用同一份成稿。</small></span>
            <button
              class="phrases-primary"
              :disabled="working || busy || !changeCount"
              @click="save"
            >
              {{ saving ? '正在保存…' : '保存短语修改' }}
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
const props = defineProps({ canGenerate: Boolean, busy: Boolean })
const emit = defineEmits(['saved'])
const endpoint = '/api/inspection-reports/safety-phrases'
const expanded = ref(false),
  data = ref(null),
  draft = ref({}),
  mode = ref('onsite'),
  keyword = ref('')
const loading = ref(false),
  saving = ref(false),
  generating = ref(false),
  error = ref(''),
  notice = ref(''),
  dialog = ref(null)
const modes = [
  { key: 'onsite', label: '现场检查', field: '检查内容' },
  { key: 'video', label: '视频检查', field: '评分项' },
]
const statusLabels = { manual: '人工修订', ai: 'AI 已生成', default: '既有短语', missing: '待补齐' }
const rows = computed(() => data.value?.rows || [])
const working = computed(() => loading.value || saving.value || generating.value)
const changes = computed(() =>
  Object.fromEntries(
    rows.value
      .filter((row) => draft.value[row.key] !== row.phrase)
      .map((row) => [row.key, draft.value[row.key]]),
  ),
)
const changeCount = computed(() => Object.keys(changes.value).length)
const pending = computed(
  () => rows.value.filter((row) => row.mode === 'video' && !row.phrase).length,
)
const visible = computed(() =>
  rows.value.filter(
    (row) =>
      row.mode === mode.value &&
      `${row.source} ${row.standard_ids.join(' ')} ${draft.value[row.key]}`
        .toLowerCase()
        .includes(keyword.value.trim().toLowerCase()),
  ),
)
const savedLabel = computed(() =>
  data.value?.meta?.updated_by_name
    ? `最近保存：${data.value.meta.updated_by_name} · ${data.value.meta.updated_at}`
    : '尚无人工修订，当前采用既有短语或 AI 结果',
)
let controller,
  sequence = 0,
  alive = true,
  previousFocus,
  bodyOverflow
function adopt(value) {
  data.value = value
  draft.value = Object.fromEntries((value.rows || []).map((row) => [row.key, row.phrase]))
}
async function open() {
  previousFocus = document.activeElement
  bodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  expanded.value = true
  await nextTick()
  dialog.value?.focus()
  await load()
}
function close() {
  if (saving.value || generating.value) return
  sequence++
  controller?.abort()
  loading.value = false
  expanded.value = false
  if (bodyOverflow !== undefined) document.body.style.overflow = bodyOverflow
  bodyOverflow = undefined
  previousFocus?.focus()
  if (data.value) adopt(data.value)
}
async function reload() {
  if (data.value) adopt(data.value)
  await load()
}
function trapFocus(event) {
  const nodes = [...dialog.value.querySelectorAll('button:not(:disabled), input:not(:disabled)')]
  if (
    document.activeElement === dialog.value ||
    document.activeElement === (event.shiftKey ? nodes[0] : nodes.at(-1))
  ) {
    event.preventDefault()
    ;(event.shiftKey ? nodes.at(-1) : nodes[0])?.focus()
  }
}
async function load() {
  if (working.value || changeCount.value) return
  const id = ++sequence
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get(endpoint, { signal: controller.signal })
    if (alive && id === sequence) adopt(response.data)
  } catch (err) {
    if (alive && id === sequence && !axios.isCancel(err))
      error.value = err.response?.data?.error || '统计短语读取失败。'
  } finally {
    if (alive && id === sequence) loading.value = false
  }
}
async function submit(method) {
  if (working.value || !data.value || props.busy) return
  if (method === 'post' && (!props.canGenerate || !data.value.can_generate || changeCount.value))
    return
  if (
    method === 'put' &&
    Object.values(changes.value).some((value) => !value?.trim() || value.trim().length > 30)
  ) {
    error.value = '统计短语不能为空且不能超过30字。'
    return
  }
  const marker = method === 'post' ? generating : saving
  marker.value = true
  error.value = notice.value = ''
  try {
    const response = await axios[method](endpoint, {
      catalog_signature: data.value.catalog_signature,
      revision: data.value.meta.revision,
      ...(method === 'put' ? { changes: changes.value } : {}),
    })
    if (!alive) return
    adopt(response.data)
    notice.value =
      method === 'put'
        ? '短语已保存，重新生成报告后应用。'
        : '视频评分项短语已准备好，后续直接复用历史结果。'
    emit('saved')
  } catch (err) {
    if (alive) error.value = err.response?.data?.error || '处理失败，请稍后重试。'
  } finally {
    if (alive) marker.value = false
  }
}
const save = () => submit('put'),
  generate = () => submit('post')
onBeforeUnmount(() => {
  alive = false
  controller?.abort()
  if (bodyOverflow !== undefined) document.body.style.overflow = bodyOverflow
})
</script>

<style scoped>
.phrases-tool {
  grid-column: 1 / -1;
  padding: 22px;
  background: #f0f6fa;
  border: 1px solid #c8dce9;
  border-radius: 14px;
  color: #294b65;
}
.phrases-tool > small {
  font-weight: 700;
  font-size: 13px;
  letter-spacing: 0.5px;
}
.phrases-tool h3 {
  margin: 10px 0;
  font-size: 19px;
}
.phrases-tool p {
  margin: 0 0 16px;
  line-height: 1.7;
}
.phrases-tool button,
.phrases-dialog button {
  border: 1px solid #b8cede;
  border-radius: 9px;
  padding: 10px 16px;
  background: white;
  color: #294b65;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.phrases-overlay {
  position: fixed;
  inset: 0;
  background: #0b233a9e;
  backdrop-filter: blur(3px);
  z-index: 1500;
  display: grid;
  place-items: center;
  padding: 24px;
}
.phrases-dialog {
  width: min(1180px, 100%);
  max-height: calc(100dvh - 48px);
  display: flex;
  flex-direction: column;
  background: #f5f8fb;
  color: #294b65;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 24px 80px #061a3659;
}
.phrases-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 24px 28px;
  background: linear-gradient(110deg, #10344e, #236678);
  color: white;
}
.phrases-dialog header h2 {
  margin: 6px 0;
  font-size: 24px;
}
.phrases-dialog header p {
  margin: 0;
  line-height: 1.6;
  color: #d0e4ef;
}
.phrases-dialog .phrases-close {
  min-width: 40px;
  padding: 5px;
  font-size: 25px;
  background: #ffffff1f;
  color: white;
  border-color: #ffffff50;
}
.phrases-layout {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  min-height: 0;
  flex: 1;
  overflow: auto;
}
.phrases-layout nav {
  padding: 24px 16px;
  background: #eaf1f7;
  border-right: 1px solid #d3e0e9;
}
.phrases-layout nav button {
  width: 100%;
  text-align: left;
  margin-bottom: 12px;
  display: grid;
  gap: 5px;
  padding: 16px;
}
.phrases-layout nav button.selected {
  background: #1d617b;
  border-color: #1d617b;
  color: white;
}
.phrases-layout nav p {
  font-size: 13px;
  line-height: 1.8;
  padding: 0 6px;
}
.phrases-main {
  min-width: 0;
  padding: 22px;
}
.phrases-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: end;
}
.phrases-toolbar label {
  flex: 1;
  min-width: 180px;
  display: grid;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}
.phrases-dialog input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #bdcfdd;
  border-radius: 8px;
  background: white;
  color: #183d58;
  padding: 11px 12px;
  font: inherit;
}
.phrases-list-summary {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #536f83;
  margin: 18px 0 12px;
}
.phrases-rows {
  display: grid;
  gap: 12px;
}
.phrases-rows article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.9fr);
  gap: 24px;
  border: 1px solid #d4e0e9;
  border-radius: 12px;
  padding: 18px;
  background: white;
}
.phrases-rows article.edited {
  border-color: #d5ac5d;
  background: #fffcf3;
}
.phrases-source > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.phrases-source p {
  line-height: 1.7;
  font-size: 14px;
  margin-bottom: 0;
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.phrases-status {
  flex-shrink: 0;
  font-size: 12px;
  background: #edf2f7;
  padding: 4px 7px;
  border-radius: 5px;
}
.phrases-status.ai,
.phrases-status.manual {
  color: #17665f;
  background: #e3f3ed;
}
.phrases-status.missing {
  background: #fff0d8;
  color: #8a5e16;
}
.phrases-edit {
  display: grid;
  gap: 9px;
  align-content: start;
  font-size: 13px;
  font-weight: 600;
}
.phrases-edit small {
  color: #627b8b;
  font-weight: 400;
  line-height: 1.6;
}
.phrases-dialog footer {
  padding: 18px 26px;
  border-top: 1px solid #d3e0ea;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  font-size: 13px;
}
.phrases-dialog footer small {
  display: block;
  color: #6b8395;
  margin-top: 6px;
}
.phrases-dialog .phrases-primary {
  background: #246a8a;
  color: white;
  border-color: #246a8a;
}
.phrases-dialog button:hover:not(:disabled),
.phrases-tool button:hover:not(:disabled) {
  filter: brightness(0.95);
}
.phrases-dialog button:disabled,
.phrases-tool button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.phrases-dialog :focus-visible {
  outline: 3px solid #66acc5;
  outline-offset: 2px;
}
.phrases-error,
.phrases-notice {
  padding: 12px;
  border-radius: 8px;
  line-height: 1.6;
}
.phrases-error {
  background: #fff0ed;
  color: #a93f2b;
}
.phrases-notice {
  background: #e8f5ee;
  color: #23664e;
}
.phrases-state {
  padding: 32px;
  text-align: center;
}
@media (max-width: 700px) {
  .phrases-overlay {
    padding: 10px;
  }
  .phrases-dialog {
    max-height: calc(100dvh - 20px);
  }
  .phrases-dialog header {
    padding: 18px;
  }
  .phrases-layout {
    grid-template-columns: 1fr;
  }
  .phrases-layout nav {
    display: flex;
    gap: 10px;
    padding: 12px;
    border-right: 0;
  }
  .phrases-layout nav button {
    margin: 0;
    padding: 12px;
  }
  .phrases-layout nav p {
    display: none;
  }
  .phrases-main {
    padding: 14px;
  }
  .phrases-rows article {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 14px;
  }
  .phrases-dialog footer {
    padding: 14px;
    flex-wrap: wrap;
  }
}
</style>
