<template>
  <div class="page-shell expert-page">
    <header class="page-header card-surface">
      <div>
        <div class="page-kicker">运营系统 / KNOWLEDGE DESK</div>
        <h2>专家问答</h2>
        <p class="page-desc">从规范到业务事实，让每个回答有据可查。</p>
      </div>
      <span class="status-pill info">{{ meta.model || '所选大模型' }} · 知识检索增强</span>
    </header>
    <button
      class="knowledge-toggle"
      type="button"
      :aria-expanded="showKnowledge"
      @click="showKnowledge = !showKnowledge"
    >
      {{ showKnowledge ? '收起查询范围与知识源' : '查询范围与知识源' }} ·
      {{ allHistory ? '全部历史' : options.date_from + ' 至 ' + options.date_to }}
    </button>
    <div class="expert-grid">
      <aside class="knowledge-panel card-surface" :class="{ 'knowledge-expanded': showKnowledge }">
        <div class="panel-title">
          <span class="panel-index">01</span>
          <h3>提问范围</h3>
        </div>
        <p class="scope-notice">
          {{ meta.scope || '查询全局业务资料，不沿用其他菜单的片区与检查表限制。' }}
        </p>
        <label class="all-history"
          ><input v-model="allHistory" type="checkbox" :disabled="busy" /> 查询全部登记历史</label
        >
        <div class="date-pair">
          <label
            >开始日期<input v-model="options.date_from" type="date" :disabled="busy || allHistory"
          /></label>
          <label
            >结束日期<input v-model="options.date_to" type="date" :disabled="busy || allHistory"
          /></label>
        </div>
        <label class="region-field"
          >站点所属片区<input
            v-model.trim="options.region"
            :disabled="busy"
            placeholder="留空查询全部；请输入完整片区名称"
            maxlength="100"
        /></label>
        <p class="muted">
          日期只限制问题、亮点登记和巡检记录。规范、计划周期、证照有效期与报告成稿不受此日期限制。
        </p>
        <div class="panel-title">
          <span class="panel-index">02</span>
          <h3>知识与业务资料</h3>
        </div>
        <div class="source-inventory">
          <span v-for="kind in meta.sources" :key="kind"><i></i>{{ kind }}</span>
        </div>
        <p class="muted">
          不读取密码、登录凭据、密钥或备份内容。文档仅提取可读取文字，不识别照片或扫描页。
        </p>
        <div class="panel-title">
          <span class="panel-index">03</span>
          <h3>从这里开始</h3>
        </div>
        <button
          v-for="example in examples"
          :key="example"
          type="button"
          class="example"
          :disabled="busy"
          @click="question = example"
        >
          {{ example }}<span>↗</span>
        </button>
      </aside>
      <section class="conversation-panel card-surface">
        <div class="conversation-header">
          <div>
            <h3>业务咨询台</h3>
            <p>回答仅作辅助参考，关键判断请核对原始资料。</p>
          </div>
          <button class="btn btn-light" :disabled="busy || loading" @click="newConversation">
            新建问答
          </button>
        </div>
        <div v-if="error" class="error-notice" role="alert">{{ error }}</div>
        <div v-if="loading" class="empty-conversation" role="status">正在读取最近问答…</div>
        <div v-else-if="!items.length" class="empty-conversation">
          <span class="empty-symbol">问</span>
          <h3>把一个业务问题，交给真实资料回答</h3>
          <p>可以询问规范要求、问题分布、整改与申诉流程，或某座站点的相关记录。</p>
        </div>
        <div v-else ref="turns" class="turns">
          <article v-for="item in items" :key="item.id" class="turn">
            <div class="question-bubble">
              <span class="turn-label"
                >你的提问 <time>{{ item.created_at }}</time></span
              >
              <p>{{ item.question }}</p>
              <small>{{ rangeLabel(item.options) }}</small>
            </div>
            <div class="answer-content">
              <div v-if="pending(item.status)" class="answer-progress" role="status">
                <i></i><strong>{{ stages[item.status] }}</strong>
                <p>后台处理中，离开页面后可从最近问答继续查看。</p>
              </div>
              <p v-else-if="item.status === 'failed'" class="error-notice">
                {{ item.error_message || '回答未完成，请重新提问。' }}
              </p>
              <template v-else-if="item.result">
                <div class="answer-meta">
                  <span>专家回答</span
                  ><small
                    >{{
                      item.result.cache_hit
                        ? '已复用相同问题与资料的历史答案 · 未调用AI'
                        : '已调用 ' + item.result.model
                    }}
                    · {{ item.updated_at }}</small
                  >
                </div>
                <div
                  v-for="(paragraph, index) in item.result.answer.paragraphs"
                  :key="index"
                  class="answer-paragraph"
                >
                  <p>{{ paragraph.text }}</p>
                  <a
                    v-for="ref in paragraph.sources"
                    :key="ref"
                    :href="'#' + item.id + '-' + ref"
                    class="citation"
                    @click.prevent="focusSource(item.id, ref)"
                    >{{ ref }}</a
                  >
                </div>
                <p v-if="item.result.answer.caveat" class="caveat">
                  {{ item.result.answer.caveat }}
                </p>
                <details class="evidence-panel">
                  <summary>
                    核对回答依据 <span>{{ item.result.sources.length }} 份来源</span>
                  </summary>
                  <div class="retrieval-note">
                    <p>
                      这是回答时保存的证据快照，不会随业务变化实时改写；需核对最新数据时请重新提问。
                    </p>
                    <p>{{ item.result.retrieval.limits }}</p>
                    <p v-for="note in item.result.retrieval.notices" :key="note">{{ note }}</p>
                  </div>
                  <details
                    v-for="source in item.result.sources"
                    :id="item.id + '-' + source.id"
                    :key="source.id"
                    class="evidence-item"
                  >
                    <summary>
                      <b>{{ source.id }}</b
                      ><span>{{ source.title }}</span
                      ><small>{{ source.kind }}</small>
                    </summary>
                    <pre>{{ source.text }}</pre>
                  </details>
                </details>
                <button
                  class="follow-up"
                  type="button"
                  :disabled="busy"
                  @click="chooseParent(item)"
                >
                  {{ parentId === item.id ? '正在针对此答案追问' : '针对此答案追问' }}
                </button>
              </template>
            </div>
          </article>
        </div>
        <form class="composer" @submit.prevent="submit">
          <div v-if="parentId" class="follow-up-label">
            追问上一个答案 <button type="button" @click="parentId = ''">取消追问</button>
          </div>
          <label class="sr-only" for="expert-question">输入业务问题</label>
          <textarea
            id="expert-question"
            ref="composer"
            v-model="question"
            maxlength="1500"
            rows="3"
            :disabled="busy"
            placeholder="例如：卸油前铅封核对有什么规范要求？本月登记了多少问题？"
            @keydown.ctrl.enter.prevent="submit"
            @keydown.meta.enter.prevent="submit"
          ></textarea>
          <div class="composer-footer">
            <span>{{ question.length }}/1500 · Ctrl / ⌘ + Enter 提问</span
            ><button
              class="btn btn-primary"
              :disabled="busy || loading || question.trim().length < 2"
            >
              {{ busy ? '正在检索与回答…' : '发送提问' }}
            </button>
          </div>
          <small
            >每个账号每日最多30次，同一时间处理一条；最近20条问答仅本人可见。请勿输入密码或敏感个人信息。</small
          >
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, nextTick } from 'vue'
import axios from 'axios'

const localDate = (value) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
const today = new Date()
const options = reactive({
  date_from: localDate(new Date(today.getFullYear(), today.getMonth(), 1)),
  date_to: localDate(today),
  region: '',
})
const meta = reactive({ sources: [], model: '', scope: '' })
const showKnowledge = ref(false)
const turns = ref(null)
const question = ref(''),
  items = ref([]),
  loading = ref(true),
  sending = ref(false),
  error = ref(''),
  allHistory = ref(false),
  parentId = ref(''),
  composer = ref(null)
const stages = {
  queued: '正在准备查询',
  retrieving: '正在检索知识库与业务数据',
  answering: '正在依据资料整理回答',
}
const pending = (status) => Object.hasOwn(stages, status)
const busy = computed(() => sending.value || items.value.some((item) => pending(item.status)))
const examples = [
  '卸油前铅封核对有什么规范要求？',
  '本月登记了多少问题，审核情况如何？',
  '申诉被驳回后，站点应如何处理？',
]
let timer,
  controller,
  disposed = false
const rangeLabel = (value) =>
  `${value.date_from ? value.date_from + ' 至 ' + value.date_to : '全部登记历史'} · ${value.region || '全部片区'} · 全局业务资料`
function applyItem(item) {
  const index = items.value.findIndex((row) => row.id === item.id)
  const followBottom =
    index < 0 ||
    (turns.value &&
      turns.value.scrollHeight - turns.value.scrollTop - turns.value.clientHeight < 80)
  if (index < 0) items.value.push(item)
  else items.value[index] = item
  if (items.value.length > 20) items.value.splice(0, items.value.length - 20)
  if (followBottom) scrollToLatest()
}
function scrollToLatest() {
  nextTick(() => {
    if (!disposed && turns.value) turns.value.scrollTop = turns.value.scrollHeight
  })
}
function focusSource(id, ref) {
  const source = document.getElementById(id + '-' + ref)
  if (!source) return
  source.open = true
  const panel = source.closest('.evidence-panel')
  if (panel) panel.open = true
  source.scrollIntoView({ block: 'center' })
}
async function poll(id) {
  clearTimeout(timer)
  if (disposed) return
  try {
    controller = new AbortController()
    const response = await axios.get(`/api/operations/expert/questions/${id}`, {
      signal: controller.signal,
      timeout: 15000,
    })
    if (disposed) return
    applyItem(response.data.item)
    if (pending(response.data.item.status)) timer = setTimeout(() => poll(id), 2500)
    else if (response.data.item.status === 'completed') parentId.value = id
  } catch (failure) {
    if (disposed) return
    error.value = failure.response?.data?.error || '结果读取暂时失败，正在重试；无需重复发送问题。'
    if ([401, 403, 404].includes(failure.response?.status)) {
      items.value = []
      return
    }
    timer = setTimeout(() => poll(id), 10000)
  }
}
async function submit() {
  if (busy.value || question.value.trim().length < 2 || disposed) return
  if (
    !allHistory.value &&
    (!options.date_from || !options.date_to || options.date_from > options.date_to)
  ) {
    error.value = '请选择有效的开始和结束日期。'
    return
  }
  sending.value = true
  error.value = ''
  try {
    controller = new AbortController()
    const response = await axios.post(
      '/api/operations/expert/questions',
      {
        question: question.value.trim(),
        parent_id: parentId.value,
        ...options,
        date_from: allHistory.value ? '' : options.date_from,
        date_to: allHistory.value ? '' : options.date_to,
      },
      { signal: controller.signal, timeout: 20000 },
    )
    if (disposed) return
    applyItem({
      id: response.data.id,
      question: question.value.trim(),
      options: {
        ...options,
        date_from: allHistory.value ? '' : options.date_from,
        date_to: allHistory.value ? '' : options.date_to,
      },
      status: 'queued',
      created_at: '刚刚',
    })
    question.value = ''
    poll(response.data.id)
  } catch (failure) {
    if (!disposed)
      error.value =
        failure.response?.data?.error || '发送未确认，请重新进入本页核对历史记录，避免重复提问。'
  } finally {
    sending.value = false
  }
}
async function chooseParent(item) {
  parentId.value = item.id
  await nextTick()
  composer.value?.focus()
}
async function newConversation() {
  parentId.value = ''
  question.value = ''
  await nextTick()
  composer.value?.focus()
}
onMounted(async () => {
  try {
    controller = new AbortController()
    const config = await axios.get('/api/operations/expert/meta', {
      signal: controller.signal,
      timeout: 15000,
    })
    if (disposed) return
    Object.assign(meta, config.data)
    const response = await axios.get('/api/operations/expert/questions', {
      signal: controller.signal,
      timeout: 15000,
    })
    if (disposed) return
    items.value = response.data.items.reverse()
    scrollToLatest()
    const active = items.value.find((item) => pending(item.status))
    if (active) poll(active.id)
  } catch (failure) {
    if (!disposed)
      error.value = failure.response?.data?.error || '专家问答读取失败，请稍后重新打开。'
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  disposed = true
  clearTimeout(timer)
  controller?.abort()
})
</script>

<style scoped>
.page-shell {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.card-surface {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dbe4ee;
  border-radius: 22px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  padding: 24px 28px;
}
.page-kicker {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  background: #eaf4fb;
  color: #126f98;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0;
  font-size: 34px;
  color: #0f172a;
}
.page-desc {
  color: #64748b;
  line-height: 1.8;
  margin-bottom: 0;
}
.status-pill {
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 12px;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #dbeafe;
  white-space: nowrap;
}
.btn {
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid #d7e0ea;
  border-radius: 12px;
  background: #f8fafc;
  color: #17334b;
  font-weight: 800;
  cursor: pointer;
}
.btn-primary {
  color: white;
  border-color: #126f98;
  background: linear-gradient(135deg, #126f98, #269bbb);
}
.btn:focus-visible,
.example:focus-visible,
.follow-up:focus-visible {
  outline: 2px solid #76b3ca;
  outline-offset: 3px;
}
.knowledge-toggle {
  display: none;
  border: 1px solid #c5dfe8;
  border-radius: 10px;
  background: #f3fafc;
  color: #176e91;
  padding: 12px;
  text-align: left;
}
.expert-page {
  --expert-ink: #17334b;
  --expert-blue: #126f98;
  --expert-border: #dce7ed;
}
.expert-grid {
  display: grid;
  grid-template-columns: 310px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.knowledge-panel {
  padding: 24px;
  background: linear-gradient(155deg, #f4fafc, #fff 65%);
}
.panel-title {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 24px 0 14px;
}
.panel-title:first-child {
  margin-top: 0;
}
.panel-title h3 {
  font-size: 15px;
  margin: 0;
}
.panel-index {
  font:
    600 12px Georgia,
    serif;
  color: #50849b;
  border-bottom: 2px solid #90c9d9;
  padding-bottom: 3px;
}
.scope-notice {
  font-size: 13px;
  line-height: 1.8;
  color: #765115;
  background: #fff7e8;
  border: 1px solid #efdcb6;
  border-radius: 10px;
  padding: 12px;
}
.all-history {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  margin: 20px 0 14px;
}
.date-pair {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.date-pair label,
.region-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: #567080;
}
.region-field {
  margin-top: 14px;
}
input:not([type='checkbox']) {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 10px 8px;
  border: 1px solid var(--expert-border);
  border-radius: 8px;
  background: white;
  color: var(--expert-ink);
}
.muted {
  color: #6c7f8b;
  font-size: 12px;
  line-height: 1.8;
}
.source-inventory {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}
.source-inventory span {
  padding: 6px 9px;
  border: 1px solid var(--expert-border);
  background: #fff;
  border-radius: 6px;
  font-size: 12px;
}
.source-inventory i {
  display: inline-block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #2a8d9c;
  margin: 0 6px 2px 0;
}
.example {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 12px 0;
  border: none;
  border-bottom: 1px solid var(--expert-border);
  color: var(--expert-blue);
  background: none;
  cursor: pointer;
  line-height: 1.7;
  font-size: 13px;
}
.example span {
  flex-shrink: 0;
}
.conversation-panel {
  overflow: hidden;
  min-width: 0;
}
.conversation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  padding: 24px 28px;
  border-bottom: 1px solid var(--expert-border);
  background: linear-gradient(120deg, #fff, #f0f7fa);
}
.conversation-header h3 {
  margin: 0;
  color: var(--expert-ink);
}
.conversation-header p {
  font-size: 12px;
  color: #647f90;
  margin: 8px 0 0;
}
.empty-conversation {
  padding: 65px 35px;
  text-align: center;
  color: #6c7f8b;
}
.empty-conversation h3 {
  color: var(--expert-ink);
  font-size: 18px;
}
.empty-conversation p {
  line-height: 1.8;
  font-size: 13px;
}
.empty-symbol {
  display: inline-grid;
  place-items: center;
  width: 65px;
  height: 65px;
  border: 1px solid #c5dfe8;
  border-radius: 20px;
  background: linear-gradient(140deg, #ecf9ff, #fff);
  color: var(--expert-blue);
  font-size: 27px;
}
.turns {
  max-height: min(64dvh, 740px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 25px 28px;
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.turn {
  min-width: 0;
}
.question-bubble {
  background: #f1f6fa;
  border: 1px solid #e4edf3;
  border-radius: 14px 14px 3px 14px;
  padding: 15px 18px;
  margin-left: 45px;
}
.question-bubble p {
  margin: 8px 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.turn-label {
  font-size: 12px;
  color: #547388;
}
.turn-label time {
  margin-left: 12px;
  color: #82929c;
}
.question-bubble small {
  color: #7f909b;
  font-size: 11px;
}
.answer-content {
  padding: 18px 0 0;
}
.answer-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 15px;
  align-items: center;
  color: var(--expert-blue);
  font-size: 13px;
}
.answer-meta small {
  color: #7a8f9c;
  font-size: 11px;
}
.answer-paragraph p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.9;
  font-size: 14px;
  color: #243b4e;
  margin: 16px 0 5px;
}
.citation {
  display: inline-block;
  margin-right: 5px;
  color: var(--expert-blue);
  font-size: 11px;
  background: #eaf4f8;
  padding: 2px 6px;
  border-radius: 4px;
  text-decoration: none;
}
.caveat,
.retrieval-note {
  padding: 12px;
  color: #627886;
  background: #f7f9fb;
  font-size: 12px;
  line-height: 1.8;
  border-radius: 8px;
}
.retrieval-note p {
  margin: 4px 0;
}
.evidence-panel {
  margin-top: 18px;
  border: 1px solid var(--expert-border);
  border-radius: 10px;
  padding: 13px;
}
.evidence-panel > summary {
  color: var(--expert-ink);
  font-size: 13px;
  cursor: pointer;
}
.evidence-panel > summary span {
  font-size: 11px;
  margin-left: 10px;
  color: #8096a2;
}
.evidence-item {
  padding: 12px 0;
  border-top: 1px solid #eaf0f3;
}
.evidence-item summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  cursor: pointer;
  font-size: 12px;
}
.evidence-item summary b {
  color: var(--expert-blue);
}
.evidence-item summary small {
  color: #78909d;
}
.evidence-item pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.8;
  background: #f8fafb;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
}
.follow-up {
  border: none;
  background: none;
  color: var(--expert-blue);
  font-size: 12px;
  cursor: pointer;
  padding: 12px 0;
}
.answer-progress {
  padding: 18px;
  border-left: 3px solid #7cb9cd;
  background: #f4fafc;
  font-size: 13px;
}
.answer-progress i {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 10px;
  background: #2386a6;
  border-radius: 50%;
  animation: pulse 1.8s infinite;
}
.answer-progress p {
  color: #6b8695;
  font-size: 12px;
  margin-bottom: 0;
}
.error-notice {
  margin: 15px 28px;
  padding: 12px;
  background: #fff3f1;
  color: #a84735;
  border-radius: 8px;
  font-size: 13px;
}
.composer {
  border-top: 1px solid var(--expert-border);
  padding: 22px 28px;
  background: #fbfdfe;
}
.composer textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  min-height: 90px;
  max-height: 250px;
  padding: 15px;
  border: 1px solid #c8dfe9;
  border-radius: 12px;
  font: inherit;
  font-size: 14px;
  line-height: 1.7;
  background: white;
}
.composer textarea:focus {
  outline: 2px solid #76b3ca;
  outline-offset: 2px;
}
.composer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}
.composer-footer span,
.composer > small {
  font-size: 11px;
  color: #8a9ba5;
}
.composer > small {
  display: block;
  margin-top: 12px;
}
.follow-up-label {
  color: #41748c;
  font-size: 12px;
  margin-bottom: 10px;
}
.follow-up-label button {
  background: none;
  border: none;
  color: #8b9ba5;
  cursor: pointer;
  margin-left: 12px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}
@media (prefers-reduced-motion: reduce) {
  .answer-progress i {
    animation: none;
  }
}
@media (max-width: 1100px) {
  .expert-grid {
    grid-template-columns: 250px minmax(0, 1fr);
  }
  .knowledge-panel {
    padding: 18px;
  }
  .date-pair {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 760px) {
  .knowledge-toggle {
    display: block;
  }
  .knowledge-panel:not(.knowledge-expanded) {
    display: none;
  }
  .page-header {
    flex-direction: column;
    padding: 20px;
  }
  .page-header h2 {
    font-size: 28px;
  }
  .expert-grid {
    grid-template-columns: 1fr;
  }
  .date-pair {
    grid-template-columns: 1fr 1fr;
  }
  .source-inventory {
    gap: 6px;
  }
  .conversation-header,
  .turns,
  .composer {
    padding: 18px;
  }
  .conversation-header {
    align-items: flex-start;
  }
  .conversation-header .btn {
    white-space: nowrap;
  }
  .question-bubble {
    margin-left: 15px;
  }
  .composer-footer {
    flex-wrap: wrap;
  }
  .composer-footer button {
    width: 100%;
  }
  .empty-conversation {
    padding: 35px 20px;
  }
}
</style>
