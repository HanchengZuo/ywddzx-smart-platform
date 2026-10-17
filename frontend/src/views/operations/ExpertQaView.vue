<template>
  <div class="page-shell expert-page">
    <header class="page-header card-surface">
      <div>
        <div class="page-kicker">运营系统 / KNOWLEDGE DESK</div>
        <h2>专家问答</h2>
        <p>直接提问，连接全部系统业务数据与知识。回答有依据，追问有上下文。</p>
      </div>
      <div class="header-status">
        <span class="status-dot"></span>
        <div>
          <strong>{{ meta.model || '所选大模型' }}</strong
          ><small>全局业务资料 · 检索增强</small>
        </div>
      </div>
    </header>

    <div class="mobile-toolbar">
      <button class="btn" @click="showHistory = !showHistory">
        {{ showHistory ? '收起会话' : '最近会话' }}</button
      ><button class="btn" :disabled="loading" @click="newConversation">新建问答</button>
    </div>
    <div class="expert-grid">
      <aside class="history-panel card-surface" :class="{ expanded: showHistory }">
        <button
          class="btn btn-primary new-conversation"
          :disabled="loading"
          @click="newConversation"
        >
          ＋ 新建问答
        </button>
        <label class="sr-only" for="conversation-search">搜索最近会话</label>
        <input
          id="conversation-search"
          v-model.trim="historyKeyword"
          type="search"
          class="history-search"
          placeholder="搜索最近会话"
        />
        <div class="history-heading">
          <h3>最近会话</h3>
          <span>{{ groups.length }}</span>
        </div>
        <nav class="history-list" aria-label="最近问答会话">
          <p v-if="loading" class="muted">正在读取会话…</p>
          <p v-else-if="!groups.length" class="muted">
            {{ historyKeyword ? '没有匹配的会话' : '还没有问答，从右侧开始' }}
          </p>
          <button
            v-for="group in groups"
            :key="group.id"
            class="history-item"
            :class="{ active: activeConversation === group.id }"
            :aria-current="activeConversation === group.id ? 'true' : undefined"
            @click="selectConversation(group.id)"
          >
            <strong>{{ group.title }}</strong
            ><span
              ><time>{{ group.updatedAt.slice(5, 16) }}</time
              ><small>{{ group.running ? '回答中' : group.items.length + ' 轮问答' }}</small></span
            >
          </button>
        </nav>
        <details class="knowledge-inventory">
          <summary>可检索的知识与数据</summary>
          <div class="source-inventory">
            <span v-for="kind in meta.sources" :key="kind">{{ kind }}</span>
          </div>
          <p>
            默认检索全部历史，不沿用其他页面筛选。不读取密码、密钥、登录凭据或备份内容；暂不识别照片与扫描页。
          </p>
        </details>
        <p class="history-note">仅展示本人的最近会话摘要，点击后读取回答。不会自动调用 AI。</p>
      </aside>

      <section class="conversation-panel card-surface">
        <div class="conversation-header">
          <div>
            <h3>{{ activeConversation ? '业务咨询' : '开始一次有据可查的对话' }}</h3>
            <p>
              {{
                parentId
                  ? '已连接当前会话上下文，可继续追问'
                  : '默认检索全部系统资料，无需设置提问范围'
              }}
            </p>
          </div>
          <span class="conversation-badge">全库检索</span>
        </div>
        <div v-if="error" class="error-notice" role="alert">{{ error }}</div>
        <div v-if="notice" class="copy-notice" role="status">{{ notice }}</div>
        <div v-if="loading || reading" class="empty-conversation" role="status">正在读取会话…</div>
        <div v-else-if="!items.length" class="empty-conversation">
          <span class="empty-symbol">问</span>
          <h3>查规范、看数据、理清业务流程</h3>
          <p>说明你想了解的事情即可。需要某个月或某座站点时，直接写在问题里。</p>
          <div class="starter-grid">
            <button
              v-for="example in examples"
              :key="example.text"
              class="starter"
              @click="useQuestion(example.text)"
            >
              <span>{{ example.label }}</span
              ><strong>{{ example.text }}</strong
              ><em>填入问题 ↗</em>
            </button>
          </div>
        </div>
        <div v-else ref="turns" class="turns" aria-label="问答记录">
          <article v-for="item in items" :key="item.id" class="turn">
            <div class="question-bubble">
              <span class="turn-label"
                >你的提问 <time>{{ item.created_at }}</time></span
              >
              <p>{{ item.question }}</p>
            </div>
            <div class="answer-content">
              <div v-if="pending(item.status)" class="answer-progress" role="status">
                <div class="progress-steps">
                  <span
                    v-for="(label, status) in stages"
                    :key="status"
                    :class="{ active: item.status === status }"
                    >{{ label }}</span
                  >
                </div>
                <strong><i></i>{{ stages[item.status] }}</strong>
                <p>正在后台处理，可先整理下一个问题；离开页面后仍可查看结果。</p>
              </div>
              <div v-else-if="item.status === 'failed'" class="failed-answer">
                <p class="error-notice">{{ item.error_message || '回答未完成，请重新提问。' }}</p>
                <button class="follow-up" :disabled="busy" @click="retry(item)">
                  重新填写此问题
                </button>
              </div>
              <template v-else-if="item.result">
                <div class="answer-meta">
                  <strong>专家回答</strong
                  ><small
                    >{{ item.result.cache_hit ? '复用历史答案 · 未调用AI' : item.result.model }} ·
                    {{ item.updated_at }}</small
                  ><button class="copy-answer" @click="copyAnswer(item)">复制回答</button>
                </div>
                <p v-if="scopeSummary(item.result.retrieval?.options)" class="recognized-scope">
                  本次识别的统计口径：{{ scopeSummary(item.result.retrieval.options) }}
                </p>
                <div
                  v-for="(paragraph, index) in item.result.answer.paragraphs"
                  :key="index"
                  class="answer-paragraph"
                >
                  <h4 v-if="paragraph.title">{{ paragraph.title }}</h4>
                  <p>{{ paragraph.text }}</p>
                  <a
                    v-for="ref in paragraph.sources"
                    :key="ref"
                    :href="'#' + item.id + '-' + ref"
                    class="citation"
                    :title="sourceTitle(item, ref)"
                    @click.prevent="focusSource(item.id, ref)"
                    >{{ ref }} · 依据</a
                  >
                </div>
                <p v-if="item.result.answer.caveat" class="caveat">
                  {{ item.result.answer.caveat }}
                </p>
                <details class="evidence-panel">
                  <summary>
                    核对回答依据
                    <span
                      >引用 {{ citedSources(item.result).length }} 份 / 检索
                      {{ item.result.sources.length }} 份</span
                    >
                  </summary>
                  <div class="retrieval-note">
                    <p>回答使用生成时的资料快照，不会随业务变化自动改写。</p>
                    <p v-if="item.result.retrieval?.retrieved_at">
                      资料检索时间：{{ item.result.retrieval.retrieved_at }}
                    </p>
                    <p>{{ item.result.retrieval?.method }}</p>
                    <p>{{ item.result.retrieval?.limits }}</p>
                    <p v-for="note in item.result.retrieval?.notices || []" :key="note">
                      {{ note }}
                    </p>
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
                      ><small
                        >{{ source.kind }}{{ source.locator ? ' · ' + source.locator : '' }}</small
                      >
                    </summary>
                    <pre>{{ source.text }}</pre>
                  </details>
                </details>
                <div class="answer-actions">
                  <button class="follow-up" :disabled="busy" @click="chooseParent(item)">
                    {{ parentId === item.id ? '已连接此答案，直接继续提问' : '针对此答案追问' }}
                  </button>
                </div>
                <div
                  v-if="item.result.answer.follow_up_questions?.length"
                  class="suggested-questions"
                >
                  <span>可以继续问</span
                  ><button
                    v-for="suggestion in item.result.answer.follow_up_questions"
                    :key="suggestion"
                    :disabled="busy"
                    @click="useQuestion(suggestion, item)"
                  >
                    {{ suggestion }} ↗
                  </button>
                </div>
              </template>
            </div>
          </article>
        </div>

        <form class="composer" @submit.prevent="submit">
          <div v-if="parentId" class="follow-up-label">
            <span>{{ manualParent ? '针对此答案追问' : '连续对话 · 自动联系上文' }}</span
            ><button type="button" @click="newConversation">另起新会话</button>
          </div>
          <label class="sr-only" for="expert-question">输入业务问题</label>
          <textarea
            id="expert-question"
            ref="composer"
            v-model="question"
            maxlength="1500"
            rows="3"
            placeholder="直接输入业务问题，例如：卸油前铅封核对有什么要求？本月非油问题分布如何？"
            @keydown.ctrl.enter.prevent="submit"
            @keydown.meta.enter.prevent="submit"
          ></textarea>
          <div class="composer-footer">
            <span>{{ question.length }}/1500 · Ctrl / ⌘ + Enter 发送</span
            ><button
              class="btn btn-primary"
              :disabled="busy || loading || reading || question.trim().length < 2"
            >
              {{ busy ? '有问答正在处理中…' : '发送提问' }}
            </button>
          </div>
          <small
            >每账号每日最多30次，同时处理一条；回答仅供辅助参考，关键判断请核对原文。请勿输入密码或敏感个人信息。</small
          >
        </form>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, nextTick } from 'vue'
import axios from 'axios'
import {
  answerText,
  citedSources,
  conversationId,
  groupConversations,
  isExpertPending,
  scopeSummary,
} from '@/utils/expertConversation'

const meta = reactive({ sources: [], model: '' })
const history = ref([]),
  items = ref([]),
  question = ref(''),
  historyKeyword = ref('')
const loading = ref(true),
  reading = ref(false),
  sending = ref(false),
  error = ref(''),
  notice = ref('')
const activeConversation = ref(''),
  parentId = ref(''),
  manualParent = ref(false),
  showHistory = ref(false)
const turns = ref(null),
  composer = ref(null)
const groups = computed(() => groupConversations(history.value, historyKeyword.value))
const pending = isExpertPending
const busy = computed(() => sending.value || history.value.some((item) => pending(item.status)))
const stages = { queued: '准备查询', retrieving: '检索系统资料', answering: '整理有据回答' }
const examples = [
  { label: '规范依据', text: '卸油前铅封核对有什么规范要求？' },
  { label: '数据分析', text: '本月登记了多少问题，审核情况如何？' },
  { label: '业务流程', text: '申诉被驳回后，站点应如何处理？' },
  { label: '问题追溯', text: '问题ID 6597 的完整处理过程是什么？' },
]
let timer,
  controller,
  pollController,
  postController,
  disposed = false,
  readVersion = 0
const sourceTitle = (item, id) =>
  item.result.sources.find((source) => source.id === id)?.title || id
function scrollToLatest() {
  nextTick(() => {
    if (!disposed && turns.value) turns.value.scrollTop = turns.value.scrollHeight
  })
}
function remember(item) {
  const summary = { ...item }
  delete summary.result
  const index = history.value.findIndex((row) => row.id === item.id)
  if (index < 0) history.value.unshift(summary)
  else history.value[index] = summary
}
function applyItem(item) {
  remember(item)
  if (conversationId(item) !== activeConversation.value) return
  const index = items.value.findIndex((row) => row.id === item.id)
  const followBottom =
    index < 0 ||
    (turns.value &&
      turns.value.scrollHeight - turns.value.scrollTop - turns.value.clientHeight < 100)
  if (index < 0) items.value.push(item)
  else items.value[index] = item
  if (followBottom) scrollToLatest()
  if (item.status === 'completed' && !manualParent.value) parentId.value = item.id
}
function focusSource(id, ref) {
  const source = document.getElementById(id + '-' + ref)
  if (!source) return
  source.open = true
  const panel = source.closest('.evidence-panel')
  if (panel) panel.open = true
  source.scrollIntoView({ block: 'center', behavior: 'smooth' })
}
async function selectConversation(id) {
  const version = ++readVersion
  controller?.abort()
  controller = new AbortController()
  reading.value = true
  activeConversation.value = id
  items.value = []
  parentId.value = ''
  manualParent.value = false
  error.value = ''
  showHistory.value = false
  try {
    const response = await axios.get('/api/operations/expert/questions', {
      params: { conversation_id: id },
      signal: controller.signal,
      timeout: 15000,
    })
    if (disposed || version !== readVersion) return
    items.value = [...response.data.items].reverse()
    parentId.value =
      [...items.value].reverse().find((item) => item.status === 'completed')?.id || ''
    scrollToLatest()
  } catch (failure) {
    if (!disposed && version === readVersion && !axios.isCancel(failure))
      error.value = failure.response?.data?.error || '会话读取失败，请稍后重试。'
  } finally {
    if (version === readVersion) reading.value = false
  }
}
async function poll(id) {
  clearTimeout(timer)
  if (disposed) return
  try {
    pollController = new AbortController()
    const response = await axios.get('/api/operations/expert/questions/' + id, {
      signal: pollController.signal,
      timeout: 15000,
    })
    if (disposed) return
    applyItem(response.data.item)
    if (pending(response.data.item.status)) timer = setTimeout(() => poll(id), 2500)
  } catch (failure) {
    if (disposed) return
    error.value = failure.response?.data?.error || '结果读取暂时失败，正在重试；无需重复发送问题。'
    if ([401, 403, 404].includes(failure.response?.status)) {
      history.value = history.value.filter((item) => item.id !== id)
      if ([401, 403].includes(failure.response.status)) items.value = []
      return
    }
    timer = setTimeout(() => poll(id), 10000)
  }
}
async function submit() {
  if (busy.value || loading.value || reading.value || question.value.trim().length < 2 || disposed)
    return
  const text = question.value.trim()
  const parent = parentId.value
  const sourceConversation = activeConversation.value
  const version = readVersion
  sending.value = true
  error.value = ''
  notice.value = ''
  try {
    postController = new AbortController()
    const response = await axios.post(
      '/api/operations/expert/questions',
      { question: text, parent_id: parentId.value },
      { signal: postController.signal, timeout: 20000 },
    )
    if (disposed) return
    const root = parent ? sourceConversation : response.data.id
    if (version === readVersion) {
      activeConversation.value = root
      manualParent.value = false
    }
    const title =
      history.value.find((item) => conversationId(item) === root)?.options?.conversation_title ||
      text.slice(0, 80)
    applyItem({
      id: response.data.id,
      question: text,
      options: { conversation_id: root, parent_id: parent, conversation_title: title },
      status: 'queued',
      created_at: '刚刚',
    })
    if (question.value.trim() === text) question.value = ''
    poll(response.data.id)
  } catch (failure) {
    if (!disposed)
      error.value =
        failure.response?.data?.error || '发送未确认，请重新打开会话核对记录，避免重复提问。'
  } finally {
    sending.value = false
  }
}
async function chooseParent(item) {
  parentId.value = item.id
  manualParent.value = true
  await nextTick()
  composer.value?.focus()
}
async function useQuestion(text, item) {
  question.value = text
  if (item) await chooseParent(item)
  else {
    await nextTick()
    composer.value?.focus()
  }
}
async function newConversation() {
  ++readVersion
  controller?.abort()
  reading.value = false
  activeConversation.value = ''
  parentId.value = ''
  manualParent.value = false
  items.value = []
  question.value = ''
  error.value = ''
  showHistory.value = false
  await nextTick()
  composer.value?.focus()
}
async function retry(item) {
  parentId.value = item.options?.parent_id || ''
  manualParent.value = Boolean(parentId.value)
  await useQuestion(item.question)
}
async function copyAnswer(item) {
  try {
    await navigator.clipboard.writeText(answerText(item))
    notice.value = '回答及引用来源已复制。'
  } catch {
    notice.value = '当前浏览器不支持直接复制，请选中回答文字复制。'
  }
}
onMounted(async () => {
  try {
    controller = new AbortController()
    const [config, response] = await Promise.all([
      axios.get('/api/operations/expert/meta', { signal: controller.signal, timeout: 15000 }),
      axios.get('/api/operations/expert/questions', {
        params: { summary: '1' },
        signal: controller.signal,
        timeout: 15000,
      }),
    ])
    if (disposed) return
    Object.assign(meta, config.data)
    history.value = response.data.items
    const latest = history.value[0]
    if (latest) await selectConversation(conversationId(latest))
    const active = history.value.find((item) => pending(item.status))
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
  pollController?.abort()
  postController?.abort()
})
</script>

<style scoped>
.expert-page {
  --expert-ink: #17334b;
  --expert-blue: #126f98;
  --expert-border: #dce7ed;
  display: grid;
  gap: 20px;
}
.card-surface {
  background: #fff;
  border: 1px solid var(--expert-border);
  border-radius: 20px;
  box-shadow: 0 12px 32px #17334b06;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 25px 28px;
  background: radial-gradient(ellipse at right top, #e4f2f8, transparent 60%), white;
}
.page-kicker {
  font-size: 11px;
  letter-spacing: 1.5px;
  color: var(--expert-blue);
  font-weight: 700;
}
.page-header h2 {
  margin: 8px 0;
  font-size: 28px;
  color: var(--expert-ink);
}
.page-header p {
  color: #708394;
  font-size: 13px;
  margin: 0;
  line-height: 1.8;
}
.header-status {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--expert-blue);
}
.header-status small {
  display: block;
  color: #8094a5;
  margin-top: 5px;
  font-size: 11px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #369c8d;
  box-shadow: 0 0 0 5px #369c8d10;
}
.expert-grid {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.history-panel {
  padding: 18px;
  background: linear-gradient(155deg, #f6fafc, #fff);
  position: sticky;
  top: 0;
}
.btn {
  min-height: 40px;
  border: 1px solid #d3e2eb;
  padding: 8px 16px;
  border-radius: 10px;
  color: var(--expert-ink);
  background: white;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary {
  background: linear-gradient(135deg, #126f98, #258fa6);
  border-color: #126f98;
  color: white;
}
.new-conversation {
  width: 100%;
}
.history-search {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--expert-border);
  border-radius: 9px;
  padding: 10px;
  font-size: 12px;
  margin-top: 14px;
  background: #fff;
}
.history-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #8395a6;
  font-size: 11px;
  padding: 20px 2px 8px;
}
.history-heading h3 {
  font-size: 12px;
  margin: 0;
  color: #536d82;
}
.history-list {
  display: grid;
  gap: 5px;
  max-height: 45dvh;
  overflow: auto;
}
.history-item {
  border: 1px solid transparent;
  padding: 12px 10px;
  border-radius: 10px;
  text-align: left;
  background: transparent;
  cursor: pointer;
  min-width: 0;
}
.history-item:hover {
  background: #f0f7fb;
}
.history-item.active {
  background: #e9f4fa;
  border-color: #cde2ef;
}
.history-item strong {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.7;
  color: #254b67;
  font-size: 12px;
  font-weight: 500;
}
.history-item > span {
  display: flex;
  justify-content: space-between;
  color: #8a9cab;
  font-size: 10px;
  margin-top: 8px;
}
.history-item small {
  font-size: inherit;
}
.knowledge-inventory {
  border-top: 1px solid var(--expert-border);
  margin-top: 20px;
  padding-top: 16px;
  font-size: 11px;
  color: #698397;
}
.knowledge-inventory summary {
  cursor: pointer;
}
.knowledge-inventory p,
.history-note {
  color: #8a9ba9;
  font-size: 11px;
  line-height: 1.8;
}
.source-inventory {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-top: 12px;
}
.source-inventory span {
  background: #eef5f9;
  padding: 4px 7px;
  border-radius: 4px;
}
.conversation-panel {
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.conversation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  padding: 20px 26px;
  border-bottom: 1px solid var(--expert-border);
}
.conversation-header h3 {
  font-size: 16px;
  margin: 0;
  color: var(--expert-ink);
}
.conversation-header p {
  font-size: 11px;
  color: #8095a5;
  margin: 7px 0 0;
}
.conversation-badge {
  color: #337899;
  background: #edf7fb;
  padding: 5px 8px;
  border-radius: 5px;
  font-size: 10px;
  white-space: nowrap;
}
.empty-conversation {
  text-align: center;
  padding: 35px 28px;
  color: #6f8799;
}
.empty-conversation h3 {
  color: #28475e;
  font-size: 18px;
}
.empty-conversation p {
  font-size: 12px;
  line-height: 1.8;
}
.empty-symbol {
  display: inline-grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: #edf7fb;
  border: 1px solid #d4e7f0;
  color: var(--expert-blue);
  font-size: 23px;
}
.starter-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 25px auto 0;
  max-width: 680px;
}
.starter {
  text-align: left;
  border: 1px solid #e0eaf1;
  border-radius: 12px;
  padding: 16px;
  background: white;
  cursor: pointer;
}
.starter:hover {
  border-color: #87bacd;
  background: #f9fcfd;
}
.starter span {
  font-size: 10px;
  color: #4595ae;
}
.starter strong {
  display: block;
  font-size: 12px;
  line-height: 1.8;
  color: #3b5a70;
  font-weight: 500;
  margin: 7px 0;
}
.starter em {
  font-size: 10px;
  color: #9aadb9;
  font-style: normal;
}
.turns {
  min-height: 260px;
  max-height: min(62dvh, 720px);
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.turn {
  min-width: 0;
}
.question-bubble {
  margin-left: clamp(20px, 8%, 80px);
  padding: 14px 18px;
  border: 1px solid #e0ebf1;
  background: #f2f7fa;
  border-radius: 14px 14px 3px 14px;
}
.question-bubble p {
  font-size: 14px;
  color: #29475e;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.8;
  margin: 8px 0 0;
}
.turn-label {
  font-size: 10px;
  color: #8498a8;
}
.turn-label time {
  margin-left: 10px;
}
.answer-content {
  padding-top: 20px;
}
.answer-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: var(--expert-blue);
}
.answer-meta small {
  font-size: 10px;
  color: #93a4b1;
}
.copy-answer {
  margin-left: auto;
  background: transparent;
  border: 0;
  color: #6b879b;
  font-size: 11px;
  cursor: pointer;
  padding: 4px;
}
.recognized-scope {
  font-size: 10px;
  color: #8b9eac;
  margin: 10px 0;
}
.answer-paragraph h4 {
  color: #24495f;
  font-size: 14px;
  margin: 20px 0 0;
}
.answer-paragraph p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.95;
  font-size: 14px;
  color: #2c465a;
  margin: 12px 0 6px;
}
.citation {
  display: inline-block;
  margin-right: 6px;
  background: #edf6fa;
  color: #247c9e;
  padding: 3px 7px;
  border-radius: 5px;
  text-decoration: none;
  font-size: 10px;
}
.caveat,
.retrieval-note {
  padding: 12px 14px;
  color: #7c8e9d;
  background: #f7f9fb;
  font-size: 11px;
  line-height: 1.8;
  border-radius: 8px;
}
.retrieval-note p {
  margin: 5px 0;
}
.evidence-panel {
  margin-top: 15px;
  border: 1px solid var(--expert-border);
  border-radius: 10px;
  padding: 12px;
}
.evidence-panel > summary {
  color: #4f7288;
  font-size: 12px;
  cursor: pointer;
}
.evidence-panel > summary span {
  font-size: 10px;
  margin-left: 8px;
  color: #8a9eac;
}
.evidence-item {
  border-top: 1px solid #e8eff4;
  padding: 12px 0;
}
.evidence-item summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 11px;
  color: #526e82;
  cursor: pointer;
}
.evidence-item b {
  color: var(--expert-blue);
}
.evidence-item small {
  color: #97a8b4;
}
.evidence-item pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
  font-size: 11px;
  line-height: 1.8;
  background: #f8fafb;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
}
.follow-up {
  background: transparent;
  border: 0;
  color: #277f9e;
  font-size: 11px;
  cursor: pointer;
  padding: 12px 0;
}
.suggested-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.suggested-questions > span {
  font-size: 10px;
  color: #97a8b3;
}
.suggested-questions button {
  background: white;
  border: 1px solid #dbe8ef;
  color: #578198;
  font-size: 11px;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
}
.answer-progress {
  background: #f4fafc;
  padding: 16px;
  border-radius: 10px;
  color: #3f7b96;
  font-size: 12px;
}
.answer-progress strong {
  display: block;
  padding-top: 15px;
}
.answer-progress i {
  display: inline-block;
  width: 7px;
  height: 7px;
  background: #3a9db5;
  border-radius: 50%;
  margin-right: 8px;
  animation: pulse 1.8s infinite;
}
.answer-progress p {
  font-size: 11px;
  color: #8ca2af;
}
.progress-steps {
  display: flex;
  gap: 16px;
  font-size: 10px;
  color: #9fb3c0;
}
.progress-steps span {
  padding-bottom: 5px;
  border-bottom: 2px solid #e0ebf1;
}
.progress-steps .active {
  color: #267d9c;
  border-color: #429eb7;
}
.error-notice,
.copy-notice {
  margin: 12px 24px;
  padding: 12px;
  background: #fff2ef;
  color: #a94e3c;
  border-radius: 8px;
  font-size: 12px;
}
.copy-notice {
  color: #347863;
  background: #edf8f2;
}
.failed-answer .error-notice {
  margin: 0;
}
.composer {
  border-top: 1px solid var(--expert-border);
  padding: 20px 26px;
  background: #fbfdfe;
}
.composer textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #cfe1ea;
  border-radius: 12px;
  background: white;
  padding: 14px;
  resize: vertical;
  min-height: 80px;
  max-height: 220px;
  font: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: var(--expert-ink);
}
.composer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}
.composer-footer > span,
.composer > small {
  font-size: 10px;
  color: #95a7b4;
}
.composer > small {
  display: block;
  line-height: 1.8;
  margin-top: 10px;
}
.follow-up-label {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #4b899e;
  margin-bottom: 10px;
}
.follow-up-label button {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: inherit;
  color: #849daa;
}
.muted {
  color: #9aacb8;
  font-size: 11px;
  padding: 8px;
}
.mobile-toolbar {
  display: none;
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
button:focus-visible,
a:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 2px solid #79b9ce;
  outline-offset: 3px;
}
@keyframes pulse {
  50% {
    opacity: 0.3;
  }
}
@media (prefers-reduced-motion: reduce) {
  .answer-progress i {
    animation: none;
  }
}
@media (max-width: 1100px) {
  .expert-grid {
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 14px;
  }
  .turns {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .expert-page {
    gap: 12px;
  }
  .page-header {
    padding: 20px;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }
  .page-header h2 {
    font-size: 25px;
  }
  .header-status {
    font-size: 11px;
  }
  .expert-grid {
    grid-template-columns: 1fr;
  }
  .mobile-toolbar {
    display: flex;
    justify-content: space-between;
  }
  .history-panel {
    position: static;
  }
  .history-panel:not(.expanded) {
    display: none;
  }
  .history-list {
    max-height: 36dvh;
  }
  .new-conversation {
    display: none;
  }
  .history-search {
    margin-top: 0;
  }
  .conversation-header {
    padding: 18px;
  }
  .conversation-header h3 {
    font-size: 14px;
  }
  .conversation-header p {
    line-height: 1.7;
  }
  .empty-conversation {
    padding: 25px 18px;
  }
  .starter-grid {
    grid-template-columns: 1fr;
  }
  .starter {
    padding: 14px;
  }
  .turns {
    padding: 18px;
    max-height: 58dvh;
  }
  .composer {
    padding: 16px;
  }
  .composer-footer {
    align-items: flex-end;
  }
  .composer-footer > span {
    max-width: 45%;
    line-height: 1.8;
  }
  .composer-footer .btn {
    font-size: 12px;
    padding: 9px 12px;
  }
  .question-bubble {
    margin-left: 16px;
  }
  .answer-paragraph p {
    font-size: 13px;
  }
  .evidence-panel > summary span {
    display: block;
    margin-top: 5px;
  }
  .progress-steps {
    gap: 10px;
  }
  .suggested-questions {
    align-items: stretch;
  }
  .suggested-questions > span {
    width: 100%;
  }
}
</style>
