<template>
  <div class="notification-page">
    <header class="notification-hero">
      <div>
        <span>管理系统 / MESSAGE OPERATIONS</span>
        <h2>消息通知管理</h2>
        <p>掌握开通情况，面向指定用户的所有有效设备投递。</p>
      </div>
      <button :disabled="loading" @click="load">刷新统计</button>
    </header>
    <p v-if="error" class="notification-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notification-success" role="status">{{ notice }}</p>
    <div class="notification-metrics">
      <article v-for="metric in metrics" :key="metric.key">
        <span>{{ metric.label }}</span
        ><strong>{{ summary[metric.key] || 0 }}<small>人</small></strong>
      </article>
    </div>
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
      <p class="notification-muted">
        {{ total }} 位符合条件的用户 · 已选择 {{ selected.length }} 位（最多200位）
      </p>
      <div class="notification-table-wrap">
        <table>
          <thead>
            <tr>
              <th>选择</th>
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
                <input
                  type="checkbox"
                  :checked="selected.some((entry) => entry.id === user.id)"
                  @change="toggleUser(user, $event.target.checked)"
                />
              </td>
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
          <h3>发送系统通知</h3>
          <p>
            向所选用户的全部有效订阅设备发送。用户未授权、关闭推送或设备不支持时，只保留站内通知。
          </p>
        </div>
      </header>
      <div class="notification-recipient-tags">
        <button v-for="user in selected" :key="user.id" @click="toggleUser(user, false)">
          {{ user.real_name || user.username }} ×</button
        ><span v-if="!selected.length" class="notification-muted">请先在用户清单选择接收人。</span>
      </div>
      <form class="notification-compose" @submit.prevent="send">
        <label
          >通知标题<input
            v-model="title"
            maxlength="60"
            required
            placeholder="例如：巡检业务办理提醒" /></label
        ><label
          >通知正文<textarea
            v-model="body"
            rows="4"
            maxlength="1500"
            required
            placeholder="填写要通知用户的内容；锁屏仅展示通用提醒，正文登录后可见。"
          />
        </label>
        <footer>
          <span class="notification-muted"
            >{{ body.length }} / 1500 字 · 发送行为及操作人均记录</span
          ><button
            class="primary"
            :disabled="sending || !configured || !selected.length || !title.trim() || !body.trim()"
          >
            {{ sending ? '正在入队…' : `发送给 ${selected.length} 位用户` }}
          </button>
        </footer>
      </form>
    </section>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>消息发送记录</h3>
          <p>服务接收按设备计数，不代表已显示或已阅读；“确认收到”由用户本人反馈。</p>
        </div>
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
          ><span class="ok">{{ record.confirmed }} 人确认收到</span>
        </div>
        <footer>
          <small
            >发送人 {{ record.sender_name }} ·
            {{ record.kind === 'test' ? '设备测试' : '系统通知' }}</small
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
              >{{ entry.real_name || entry.username || '' }} {{ entry.platform }} ·
              {{ entry.browser }}</strong
            ><span>{{ entry.status ? deliveryLabels[entry.status] : pushDeviceStatus(entry) }}</span
            ><small v-if="entry.last_seen_at">最近上报 {{ formatTime(entry.last_seen_at) }}</small
            ><small v-if="entry.permission"
              >浏览器权限 {{ permissionLabels[entry.permission] || entry.permission }}</small
            ><small v-if="entry.attempts"
              >已尝试 {{ entry.attempts }} 次 · HTTP {{ entry.http_status || '无响应' }}</small
            >
            <p v-if="entry.last_error">{{ entry.last_error }}</p>
          </div>
          <p v-if="!detail.loading && !detail.items.length" class="notification-muted">
            暂无有效设备投递记录。用户可能尚未授权或订阅。
          </p>
        </section>
      </div></Teleport
    >
  </div>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref, watch, nextTick } from 'vue'
import axios from 'axios'
import { newRequestId, pushDeviceStatus } from '../../utils/webPush'
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
  sending = ref(false),
  error = ref(''),
  notice = ref(''),
  selected = ref([]),
  title = ref(''),
  body = ref(''),
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
  requestId = newRequestId(),
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
watch(
  [title, body, selected],
  () => {
    requestId = newRequestId()
  },
  { deep: true },
)
async function load() {
  const id = ++generation
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/management/notifications', {
      params: { ...applied, page: page.value, log_page: logPage.value },
    })
    if (!alive || id !== generation) return
    users.value = data.items
    summary.value = data.summary
    records.value = data.records
    recordsTotal.value = data.records_total || data.records.length
    total.value = data.total
    configured.value = data.configured
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
function toggleUser(user, checked) {
  if (sending.value) return
  if (checked && selected.value.length >= 200) {
    error.value = '每次最多选择200位用户。'
    return
  }
  selected.value = checked
    ? [...selected.value.filter((entry) => entry.id !== user.id), user]
    : selected.value.filter((entry) => entry.id !== user.id)
}
async function send() {
  if (sending.value) return
  sending.value = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/management/notifications/send', {
      request_id: requestId,
      user_ids: selected.value.map((user) => user.id),
      title: title.value.trim(),
      body: body.value.trim(),
    })
    notice.value = data.message
    requestId = newRequestId()
    await load()
  } catch (err) {
    error.value = err.response?.data?.error || '发送结果未确认，请重试（相同请求不会重复入队）。'
  } finally {
    sending.value = false
  }
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
