<template>
  <div class="notification-page">
    <header class="notification-hero">
      <div>
        <span>管理系统 / MESSAGE OPERATIONS</span>
        <h2>消息通知管理</h2>
        <p>掌握开通情况，面向指定用户的所有有效设备投递。</p>
      </div>
      <div class="notification-hero-actions">
        <button :disabled="loading" @click="load">刷新统计</button
        ><button :disabled="!configured" @click="compose = true">发送通知</button>
      </div>
    </header>
    <p v-if="error" class="notification-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notification-success" role="status">{{ notice }}</p>
    <div class="notification-metrics">
      <article v-for="metric in metrics" :key="metric.key">
        <span>{{ metric.label }}</span
        ><strong>{{ summary[metric.key] || 0 }}<small>人</small></strong>
      </article>
    </div>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <span class="notification-eyebrow">BUSINESS PUSH</span>
          <h3>已接入的业务提醒</h3>
          <p>
            沿用业务红点和办理权限，不改变原有流程。新流转自动通知；办理后未发送的提醒会跳过，避免过期催办。
          </p>
        </div>
        <span class="notification-state enabled">{{ sources.length }} 项自动提醒</span>
      </header>
      <div class="notification-source-grid">
        <article
          v-for="(source, index) in sources"
          :key="source.key"
          class="notification-source-card"
        >
          <header>
            <span>{{ String(index + 1).padStart(2, '0') }} · {{ source.menu }}</span
            ><span class="notification-state enabled">已接入</span>
          </header>
          <h4>{{ source.name }}</h4>
          <p>{{ source.trigger }}</p>
          <dl>
            <dt>接收对象</dt>
            <dd>{{ source.recipient }}</dd>
            <dt>通知口径</dt>
            <dd>{{ source.rule }}</dd>
          </dl>
          <footer>
            <strong>{{ source.total }} <small>条留痕</small></strong
            ><button @click="filterLogs(source.key)">查看记录</button>
          </footer>
        </article>
      </div>
      <p class="notification-muted">
        本次只接入以上三类业务，不补发上线前的历史待签名积压。账号暂停通知或没有有效设备时，仍保留站内消息及未投递原因。
      </p>
    </section>
    <div v-if="!configured" class="notification-guidance">
      <strong>服务端尚未配置 Web Push</strong>
      <p>
        先生成并持久保存 VAPID 密钥，再设置 WEB_PUSH_VAPID_PRIVATE_KEY 和
        WEB_PUSH_SUBJECT。当前可查看统计，暂不能订阅或发送。不配置不会影响现有业务。
      </p>
    </div>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>用户开通情况</h3>
          <p>未访问过的用户属于“未开通”，不推断为不支持。状态基于设备最近一次上报。</p>
        </div>
      </header>
      <form class="notification-filters" @submit.prevent="filter">
        <label>用户姓名 / 用户名<input v-model="keyword" placeholder="搜索用户" /></label
        ><label
          >开通状态<select v-model="state">
            <option value="">全部用户</option>
            <option value="enabled">已开通</option>
            <option value="not_enabled">未开通</option>
            <option value="unsupported">需安装 / 不支持</option>
          </select></label
        ><button class="primary" :disabled="loading">开始筛选</button>
      </form>
      <p class="notification-muted">{{ total }} 位符合条件的用户</p>
      <div class="notification-table-wrap">
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>角色</th>
              <th>通知状态</th>
              <th>订阅 / 设备</th>
              <th>最近上报</th>
              <th>设备</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>
                <strong>{{ user.real_name || user.username }}</strong
                ><small>{{ user.username }}</small>
              </td>
              <td>{{ roleLabel(user.role) }}</td>
              <td>
                <span :class="['notification-state', user.state]">{{ stateLabel(user.state) }}</span
                ><small v-if="!user.enabled">账号推送已关闭</small>
              </td>
              <td>{{ user.subscriptions }} / {{ user.devices }}</td>
              <td>{{ formatTime(user.last_seen_at) }}</td>
              <td><button @click="viewDevices(user)">查看设备</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!users.length" class="notification-empty">暂无符合条件的用户</p>
      <nav class="notification-pagination">
        <button :disabled="loading || page <= 1" @click="changePage(-1)">上一页</button
        ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 30)) }}</span
        ><button :disabled="loading || page * 30 >= total" @click="changePage(1)">下一页</button>
      </nav>
    </section>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>消息发送记录</h3>
          <p>服务接收按设备计数，不代表已显示或已阅读；“确认收到”由用户本人反馈。</p>
        </div>
        <label
          >消息来源<select v-model="logSource" @change="filterLogs(logSource)">
            <option value="">全部记录</option>
            <option v-for="source in sources" :key="source.key" :value="source.key">
              {{ source.name }}
            </option>
            <option value="manual">手动通知</option>
            <option value="test">设备测试</option>
          </select></label
        >
      </header>
      <article v-for="record in records" :key="record.id" class="notification-message">
        <header>
          <h4>{{ record.title }}</h4>
          <time>{{ formatTime(record.created_at) }}</time>
        </header>
        <p>{{ record.body }}</p>
        <div class="notification-delivery-tags">
          <span>{{ record.recipients }} 位接收人</span
          ><span>服务已接收 {{ record.accepted }} 台</span
          ><span>排队 / 重试 {{ record.pending }} 台</span
          ><span>失败 / 失效 / 跳过 {{ record.failed }} 台</span
          ><span>仅站内消息 {{ record.inbox_only || 0 }} 人</span
          ><span class="ok">{{ record.confirmed }} 人确认收到</span>
        </div>
        <footer>
          <small
            >发送人 {{ record.sender_name }} · {{ sourceLabel(record)
            }}<template v-if="!Number(record.recipients)">
              · 无符合条件的接收账号，未投递</template
            ></small
          ><button @click="viewDeliveries(record)">查看投递明细</button>
        </footer>
      </article>
      <p v-if="!records.length" class="notification-empty">暂无发送记录</p>
      <nav class="notification-pagination">
        <button :disabled="loading || logPage <= 1" @click="changeLogPage(-1)">上一批记录</button
        ><span>{{ logPage }} / {{ Math.max(1, Math.ceil(recordsTotal / 30)) }}</span
        ><button :disabled="loading || logPage * 30 >= recordsTotal" @click="changeLogPage(1)">
          下一批记录
        </button>
      </nav>
    </section>
    <Teleport to="body"
      ><div v-if="detail" class="notification-overlay" @click.self="detail = null">
        <section
          ref="detailDialog"
          class="notification-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="push-detail-title"
        >
          <header>
            <h3 id="push-detail-title">{{ detail.title }}</h3>
            <button @click="detail = null" aria-label="关闭详情">×</button>
          </header>
          <p v-if="detail.loading" class="notification-muted">正在读取…</p>
          <p v-if="detail.error" class="notification-error">{{ detail.error }}</p>
          <div v-for="(entry, index) in detail.items" :key="index" class="notification-device">
            <strong
              >{{ entry.real_name || entry.username || '' }} {{ entry.platform || ''
              }}<template v-if="entry.browser"> · {{ entry.browser }}</template></strong
            ><span>{{ entry.status ? deliveryLabels[entry.status] : pushDeviceStatus(entry) }}</span
            ><small v-if="entry.last_seen_at">最近上报 {{ formatTime(entry.last_seen_at) }}</small
            ><small v-if="entry.permission"
              >浏览器权限 {{ permissionLabels[entry.permission] || entry.permission }}</small
            ><small v-if="entry.attempts"
              >已尝试 {{ entry.attempts }} 次 · HTTP {{ entry.http_status || '无响应' }}</small
            >
            <p v-if="entry.last_error">{{ entry.last_error }}</p>
            <small v-if="entry.delivery_note">入队时：{{ entry.delivery_note }}</small>
            <small v-if="entry.read_at">站内已读 {{ formatTime(entry.read_at) }}</small>
          </div>
          <p v-if="!detail.loading && !detail.items.length" class="notification-muted">
            暂无有效设备投递记录。用户可能尚未授权或订阅。
          </p>
        </section>
      </div></Teleport
    >
    <NotificationCompose v-if="compose" @close="compose = false" @sent="sent" />
  </div>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import axios from 'axios'
import { pushDeviceStatus } from '../../utils/webPush'
import NotificationCompose from '../../components/NotificationCompose.vue'
import '../../styles/notifications.css'
const users = ref([]),
  summary = ref({}),
  records = ref([]),
  logPage = ref(1),
  recordsTotal = ref(0),
  configured = ref(false),
  total = ref(0),
  page = ref(1),
  keyword = ref(''),
  state = ref(''),
  loading = ref(false),
  error = ref(''),
  notice = ref(''),
  compose = ref(false),
  sources = ref([]),
  logSource = ref(''),
  detail = ref(null)
const metrics = [
  { key: 'total', label: '有效用户' },
  { key: 'enabled', label: '已开通推送' },
  { key: 'not_enabled', label: '尚未开通' },
  { key: 'unsupported', label: '需安装 / 不支持' },
]
const deliveryLabels = {
  queued: '待发送 / 自动重试',
  sending: '发送中',
  accepted: '推送服务已接收',
  failed: '发送失败',
  expired: '订阅失效',
  skipped: '已跳过（状态变化）',
  inbox_only: '仅保留站内消息',
}
const permissionLabels = {
  granted: '已允许',
  denied: '已拒绝',
  default: '尚未授权',
  unavailable: '不可用',
}
const stateLabel = (value) =>
  ({ enabled: '已开通', not_enabled: '未开通', unsupported: '需安装 / 不支持' })[value] || value
const roleLabel = (value) =>
  ({
    root: '系统管理员',
    supervisor_manager: '督导组管理人员',
    supervisor: '督导组组员',
    station_manager: '站点',
    area_account: '片区',
    quality_safety: '质安部',
    non_oil: '非油事业部',
    oil_gas: '油气事业部',
    finance: '财务部',
    development_plan: '发展计划部',
  })[value] || value
const formatTime = (value) =>
  value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '尚未上报'
let applied = { keyword: '', status: '' },
  generation = 0,
  alive = true
const detailDialog = ref(null)
let previousFocus
watch(
  () => !!detail.value,
  async (open) => {
    if (open) {
      previousFocus = document.activeElement
      await nextTick()
      detailDialog.value?.querySelector('button')?.focus()
    } else if (previousFocus?.isConnected) previousFocus.focus()
  },
)
async function load() {
  const id = ++generation
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/management/notifications', {
      params: {
        ...applied,
        page: page.value,
        log_page: logPage.value,
        log_source: logSource.value,
      },
    })
    if (!alive || id !== generation) return
    users.value = data.items
    summary.value = data.summary
    records.value = data.records
    recordsTotal.value = data.records_total || data.records.length
    total.value = data.total
    configured.value = data.configured
    sources.value = data.sources || []
  } catch (err) {
    if (alive && id === generation) error.value = err.response?.data?.error || '通知管理读取失败。'
  } finally {
    if (alive && id === generation) loading.value = false
  }
}
const filter = () => {
  applied = { keyword: keyword.value.trim(), status: state.value }
  page.value = 1
  return load()
}
const changePage = (offset) => {
  page.value += offset
  return load()
}
const changeLogPage = (offset) => {
  logPage.value += offset
  return load()
}
const sourceLabel = (record) =>
  sources.value.find((entry) => entry.key === record.source)?.name ||
  (record.kind === 'test' ? '设备测试' : record.kind === 'manual' ? '手动通知' : '业务提醒')
const filterLogs = (source) => {
  logSource.value = source
  logPage.value = 1
  return load()
}
const sent = (message) => {
  compose.value = false
  notice.value = message
  logSource.value = ''
  logPage.value = 1
  return load()
}
async function view(url, label) {
  const current = { title: label, items: [], loading: true, error: '' }
  detail.value = current
  try {
    const { data } = await axios.get(url)
    if (detail.value?.title === label)
      detail.value = { ...current, items: data.items, loading: false }
  } catch (err) {
    if (detail.value?.title === label)
      detail.value = {
        ...current,
        loading: false,
        error: err.response?.data?.error || '读取失败。',
      }
  }
}
const viewDevices = (user) =>
  view(
    `/api/management/notifications/users/${user.id}/devices`,
    `${user.real_name || user.username} · 订阅设备`,
  )
const viewDeliveries = (record) =>
  view(`/api/management/notifications/${record.id}/deliveries`, `${record.title} · 投递明细`)
const keydown = (event) => {
  if (event.key === 'Tab' && detail.value && detailDialog.value) {
    event.preventDefault()
    detailDialog.value.querySelector('button')?.focus()
  }
  if (event.key === 'Escape') detail.value = null
}
onMounted(() => {
  load()
  window.addEventListener('keydown', keydown)
})
onBeforeUnmount(() => {
  alive = false
  generation++
  window.removeEventListener('keydown', keydown)
})
</script>
