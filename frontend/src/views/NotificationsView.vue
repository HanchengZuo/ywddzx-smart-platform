<template>
  <div class="notification-page">
    <header class="notification-hero">
      <div>
        <span>公共功能 / NOTIFICATIONS</span>
        <h2>通知中心</h2>
        <p>一个账号，多台设备。授权后，系统消息可通过浏览器推送抵达。</p>
      </div>
      <button @click="refresh" :disabled="busy">刷新状态</button>
    </header>
    <p v-if="error" class="notification-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="notification-success" role="status">{{ notice }}</p>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>当前设备</h3>
          <p>同一浏览器资料仅为最后登录的账号接收推送，其他设备不受影响。</p>
        </div>
        <label class="notification-switch"
          ><input
            type="checkbox"
            :checked="enabled"
            :disabled="busy"
            @change="setEnabled($event.target.checked)"
          />账号通知 {{ enabled ? '已开启' : '已关闭' }}</label
        >
      </header>
      <div class="notification-device-state">
        <span :class="['notification-dot', { ready: device?.active }]" />
        <div>
          <strong>{{ pushDeviceStatus(device) }}</strong>
          <p>
            浏览器权限：{{ permissionLabel }} · 服务端：{{
              configured ? '已配置' : '待管理员配置 VAPID'
            }}
          </p>
        </div>
      </div>
      <div class="notification-guidance">
        <strong>{{
          capability.code === 'ios_install_required' ? 'iPhone / iPad 开通指引' : '设备接收说明'
        }}</strong>
        <p>{{ capability.hint }}</p>
        <details class="notification-more">
          <summary>兼容性与隐私说明</summary>
          <p>
            关闭标签页后仍可推送；完全退出浏览器、断网、省电模式或系统拦截可能导致延迟或无法接收。华为及其他品牌手机请以实际能力检测和测试结果为准，不代表安装后必定可用。
          </p>
          <p>
            系统通知仅展示通用提醒，不展示业务详情。点击后需登录查看正文。开启通知不会自动授权浏览器。
          </p>
        </details>
      </div>
      <div class="notification-actions">
        <button
          class="primary"
          :disabled="busy || !configured || capability.code !== 'supported'"
          @click="enable"
        >
          开启 / 修复当前设备订阅</button
        ><button :disabled="busy || !device?.active || !enabled" @click="testPush">
          发送测试通知</button
        ><button :disabled="busy || !device?.active" @click="disable">停用当前设备</button>
      </div>
    </section>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>
            我的订阅设备 <small>{{ devices.length }}</small>
          </h3>
          <p>显示最近上报的状态；离线设备的浏览器权限可能已发生变化。</p>
        </div>
      </header>
      <div class="notification-device-grid">
        <article v-for="entry in devices" :key="entry.id" class="notification-device">
          <strong>{{ entry.platform }} · {{ entry.browser }}</strong
          ><span>{{ pushDeviceStatus(entry) }}</span
          ><small>最近连接 {{ formatTime(entry.last_seen_at) }}</small
          ><small>最近发送 {{ formatTime(entry.last_sent_at) }}</small>
          <p v-if="entry.last_error">{{ entry.last_error }}</p>
        </article>
        <p v-if="!devices.length" class="notification-muted">
          暂无设备上报，请刷新或尝试开启订阅。
        </p>
      </div>
    </section>
    <section class="notification-surface">
      <header class="notification-section-title">
        <div>
          <h3>
            系统消息 <small>{{ unread }} 条未读</small>
          </h3>
          <p>推送服务已接收不等于设备已显示。收到系统通知后，可手动确认，帮助排查设备接收情况。</p>
        </div>
      </header>
      <article
        v-for="item in items"
        :key="item.id"
        class="notification-message"
        :class="{ unread: !item.read_at }"
      >
        <header>
          <h4>{{ item.title }}</h4>
          <time>{{ formatTime(item.created_at) }}</time>
        </header>
        <p>{{ item.body }}</p>
        <div class="notification-delivery-tags">
          <span>服务已接收 {{ item.accepted }} 台</span
          ><span v-if="item.pending">待发送 / 重试 {{ item.pending }} 台</span
          ><span v-if="item.failed">失败 / 失效 / 跳过 {{ item.failed }} 台</span
          ><span v-if="item.confirmed_at" class="ok">本人已确认收到</span>
        </div>
        <footer>
          <small
            >{{ item.sender_name }} · {{ item.kind === 'test' ? '设备测试' : '系统通知' }}</small
          >
          <div>
            <button v-if="!item.read_at" :disabled="busy" @click="mark(item, false)">
              标为已读</button
            ><button v-if="!item.confirmed_at" :disabled="busy" @click="mark(item, true)">
              确认收到系统推送
            </button>
          </div>
        </footer>
      </article>
      <p v-if="!items.length" class="notification-empty">
        暂无系统消息，可以先发送一条当前设备测试通知。
      </p>
      <nav class="notification-pagination">
        <button :disabled="busy || page <= 1" @click="changePage(-1)">上一页</button
        ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span
        ><button :disabled="busy || page * 20 >= total" @click="changePage(1)">下一页</button>
      </nav>
    </section>
  </div>
</template>
<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
import {
  pushCapability,
  pushDeviceStatus,
  currentDeviceKey,
  enableDevice,
  disableDevice,
  syncDevice,
  newRequestId,
} from '../utils/webPush'
import '../styles/notifications.css'
const items = ref([]),
  devices = ref([]),
  device = ref(null),
  enabled = ref(true),
  configured = ref(false),
  publicKey = ref(''),
  total = ref(0),
  unread = ref(0),
  page = ref(1),
  busy = ref(false),
  error = ref(''),
  notice = ref('')
const capability = ref(pushCapability())
const permissionLabel = computed(
  () =>
    ({ granted: '已允许', denied: '已拒绝', default: '尚未授权' })[
      device.value?.permission || window.Notification?.permission
    ] || '不可用',
)
const formatTime = (value) =>
  value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无'
let alive = true,
  timer
async function read() {
  const [inbox, allDevices] = await Promise.all([
    axios.get('/api/notifications', { params: { page: page.value } }),
    axios.get('/api/notifications/devices'),
  ])
  if (!alive) return
  const data = inbox.data
  items.value = data.items
  total.value = data.total
  unread.value = data.unread
  enabled.value = data.enabled
  configured.value = data.configured
  publicKey.value = data.public_key
  devices.value = allDevices.data.items
}
async function action(operation) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await operation()
  } catch (err) {
    if (alive) error.value = err.response?.data?.error || err.message || '通知操作失败，请重试。'
  } finally {
    if (alive) busy.value = false
  }
}
const refresh = () =>
  action(async () => {
    capability.value = pushCapability()
    device.value = await syncDevice()
    await read()
  })
const enable = () =>
  action(async () => {
    device.value = await enableDevice(publicKey.value)
    await axios.put('/api/notifications/preference', { enabled: true })
    await read()
    notice.value = '当前设备已订阅，请发送测试通知确认实际接收。'
  })
const disable = () =>
  action(async () => {
    await disableDevice()
    device.value = await syncDevice({ active: false })
    await read()
    notice.value = '已停用当前设备；其他设备不受影响。'
  })
const setEnabled = (value) =>
  action(async () => {
    await axios.put('/api/notifications/preference', { enabled: value })
    await read()
  })
const testPush = () =>
  action(async () => {
    await axios.post('/api/notifications/test', {
      device_key: currentDeviceKey(),
      request_id: newRequestId(),
    })
    page.value = 1
    await read()
    notice.value = '测试通知已进入队列，通常30秒左右开始投递。收到系统通知后请确认。'
  })
const mark = (item, confirm) =>
  action(async () => {
    await axios.post(`/api/notifications/${item.id}/read`, { confirm })
    await read()
  })
const changePage = (offset) => {
  page.value += offset
  return action(read)
}
onMounted(() => {
  refresh()
  timer = setInterval(() => {
    if (!document.hidden && !busy.value) action(read)
  }, 15000)
})
onBeforeUnmount(() => {
  alive = false
  clearInterval(timer)
})
</script>
