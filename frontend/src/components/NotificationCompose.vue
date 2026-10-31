<template>
  <Teleport to="body">
    <div class="notification-overlay" @click.self="close">
      <section
        ref="dialog"
        class="notification-dialog notification-compose-dialog notification-page"
        role="dialog"
        aria-modal="true"
        aria-labelledby="push-compose-title"
        :aria-busy="sending"
      >
        <header>
          <div>
            <span class="notification-eyebrow">MANUAL MESSAGE</span>
            <h3 id="push-compose-title">发送系统通知</h3>
          </div>
          <button :disabled="sending" aria-label="关闭发送窗口" @click="close">×</button>
        </header>
        <p class="notification-muted">
          向所选用户的全部有效订阅设备发送。未开通推送的用户仍会收到站内消息；发送记录统一留痕。
        </p>
        <p v-if="error" class="notification-error" role="alert">{{ error }}</p>
        <div class="notification-compose-columns">
          <section class="notification-recipient-picker">
            <h4>
              选择接收人 <small>{{ selected.length }} / 200</small>
            </h4>
            <form class="notification-recipient-search" @submit.prevent="search">
              <input
                v-model="keyword"
                aria-label="搜索接收人"
                placeholder="姓名 / 用户名"
                :disabled="sending"
              />
              <button :disabled="loading || sending">搜索</button>
            </form>
            <div class="notification-recipient-list" :aria-busy="loading">
              <label
                v-for="user in users"
                :key="user.id"
                :class="{ chosen: selected.some((entry) => entry.id === user.id) }"
              >
                <input
                  type="checkbox"
                  :checked="selected.some((entry) => entry.id === user.id)"
                  :disabled="sending"
                  @change="toggle(user, $event.target.checked)"
                />
                <span
                  ><strong>{{ user.real_name || user.username }}</strong
                  ><small
                    >{{ user.username }} ·
                    {{ user.state === 'enabled' ? '已开通推送' : '仅站内消息 / 待开通' }}</small
                  ></span
                >
              </label>
              <p v-if="!users.length" class="notification-muted">
                {{ loading ? '正在读取用户…' : '暂无符合条件的用户' }}
              </p>
            </div>
            <nav class="notification-pagination">
              <button :disabled="loading || sending || page <= 1" @click="changePage(-1)">
                上一页</button
              ><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 30)) }}</span
              ><button :disabled="loading || sending || page * 30 >= total" @click="changePage(1)">
                下一页
              </button>
            </nav>
          </section>
          <form class="notification-compose" @submit.prevent="send">
            <div>
              <h4>已选接收人</h4>
              <div class="notification-recipient-tags">
                <button
                  v-for="user in selected"
                  :key="user.id"
                  type="button"
                  :disabled="sending"
                  @click="toggle(user, false)"
                >
                  {{ user.real_name || user.username }} ×</button
                ><span v-if="!selected.length" class="notification-muted"
                  >从左侧选择，可跨页多选。</span
                >
              </div>
            </div>
            <label
              >通知标题<input
                v-model="title"
                maxlength="60"
                required
                :disabled="sending"
                placeholder="例如：巡检业务办理提醒"
            /></label>
            <label
              >通知正文<textarea
                v-model="body"
                rows="6"
                maxlength="1500"
                required
                :disabled="sending"
                placeholder="填写通知内容；锁屏不展示此正文，用户登录后查看。"
              />
            </label>
            <footer>
              <span class="notification-muted">{{ body.length }} / 1500 字</span
              ><button
                class="primary"
                :disabled="sending || !selected.length || !title.trim() || !body.trim()"
              >
                {{ sending ? '正在入队…' : `发送给 ${selected.length} 位用户` }}
              </button>
            </footer>
          </form>
        </div>
      </section>
    </div>
  </Teleport>
</template>
<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import axios from 'axios'
import { newRequestId } from '../utils/webPush'

const emit = defineEmits(['close', 'sent'])
const dialog = ref(null),
  selected = ref([]),
  users = ref([]),
  keyword = ref(''),
  title = ref(''),
  body = ref(''),
  error = ref(''),
  loading = ref(false),
  sending = ref(false),
  page = ref(1),
  total = ref(0)
let requestId = newRequestId(),
  applied = '',
  generation = 0,
  alive = true,
  previousFocus,
  oldOverflow
watch(
  [title, body, selected],
  () => {
    requestId = newRequestId()
  },
  { deep: true },
)
const close = () => {
  if (!sending.value) emit('close')
}
function toggle(user, checked) {
  if (sending.value) return
  if (checked && selected.value.length >= 200) {
    error.value = '每次最多选择200位用户。'
    return
  }
  selected.value = checked
    ? [...selected.value.filter((entry) => entry.id !== user.id), user]
    : selected.value.filter((entry) => entry.id !== user.id)
}
async function load() {
  const id = ++generation
  loading.value = true
  try {
    const { data } = await axios.get('/api/management/notifications', {
      params: { keyword: applied, page: page.value, recipients_only: '1' },
    })
    if (!alive || id !== generation) return
    users.value = data.items
    total.value = data.total
  } catch (err) {
    if (alive && id === generation)
      error.value = err.response?.data?.error || '接收人读取失败，请重新搜索。'
  } finally {
    if (alive && id === generation) loading.value = false
  }
}
const search = () => {
  applied = keyword.value.trim()
  page.value = 1
  return load()
}
const changePage = (offset) => {
  page.value += offset
  return load()
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
    emit('sent', data.message)
  } catch (err) {
    error.value = err.response?.data?.error || '发送结果未确认，可直接重试，相同请求不会重复入队。'
  } finally {
    sending.value = false
  }
}
function keydown(event) {
  if (event.key === 'Escape') close()
  if (event.key !== 'Tab') return
  const targets = [
    ...dialog.value.querySelectorAll(
      'button:not(:disabled), input:not(:disabled), textarea:not(:disabled)',
    ),
  ]
  const first = targets[0],
    last = targets.at(-1)
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}
onMounted(() => {
  previousFocus = document.activeElement
  oldOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  dialog.value.querySelector('button')?.focus()
  window.addEventListener('keydown', keydown)
  load()
})
onBeforeUnmount(() => {
  alive = false
  generation++
  document.body.style.overflow = oldOverflow
  window.removeEventListener('keydown', keydown)
  if (previousFocus?.isConnected) previousFocus.focus()
})
</script>
