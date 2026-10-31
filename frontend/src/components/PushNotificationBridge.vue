<template>
  <Teleport to="body">
    <dialog
      v-if="show"
      ref="dialog"
      class="push-onboarding"
      :aria-labelledby="titleId"
      :aria-describedby="titleId + '-description'"
      @cancel.prevent="dismiss"
    >
      <header>
        <span class="push-onboarding-icon" aria-hidden="true"
          ><svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path
              d="M6 9a6 6 0 0 1 12 0v5l2 3H4l2-3V9Zm4 11h4"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            /></svg
        ></span>
        <div>
          <small>消息提醒</small>
          <h2 :id="titleId">{{ heading }}</h2>
        </div>
        <button class="push-onboarding-close" aria-label="暂不开启通知" @click="dismiss">×</button>
      </header>
      <div class="push-onboarding-content">
        <p :id="titleId + '-description'">
          {{
            mode === 'success'
              ? '当前设备已完成订阅，后续业务提醒会发送到这里。实际接收仍受网络与系统设置影响。'
              : mode === 'install'
                ? '此 iPhone / iPad 需要先添加到主屏幕，才能申请系统通知权限。'
                : '接收申诉处理、巡检验收及今日安排等与你有关的提醒。无需离开当前页面。'
          }}
        </p>
        <ol v-if="mode === 'install'" class="push-install-steps">
          <li><b>1</b><span>使用 Safari 打开本网站，点击“分享”。</span></li>
          <li><b>2</b><span>选择“添加到主屏幕”，完成添加。</span></li>
          <li><b>3</b><span>从主屏幕图标进入并登录，再点“立即开启”。</span></li>
        </ol>
        <div v-else-if="mode !== 'success'" class="push-onboarding-hint">
          <strong>{{
            permission === 'denied' ? '浏览器已拒绝通知' : '下一步将请求浏览器授权'
          }}</strong>
          <p>
            {{
              permission === 'denied'
                ? '请先在浏览器或系统设置中允许此网站通知，再重新检测；也可在通知中心查看指引。'
                : permission === 'granted'
                  ? '浏览器已允许通知，点击后为当前账号恢复此设备订阅。'
                  : '点击“立即开启”后，在浏览器提示中选择“允许”。若未出现提示，可稍后在通知中心重试。'
            }}
          </p>
        </div>
        <p v-if="error" class="push-onboarding-error" role="alert">{{ error }}</p>
        <p v-if="mode === 'success'" class="push-onboarding-success" role="status">
          已开启，可在通知中心发送测试通知。
        </p>
        <p class="push-onboarding-note">
          开通状态仅针对当前浏览器或主屏幕应用；稍后设置不会改变你的账号通知偏好。
        </p>
      </div>
      <footer>
        <button class="push-onboarding-link" @click="openCenter">通知中心 / 备用设置</button>
        <div>
          <button v-if="mode !== 'success'" @click="dismiss">稍后设置</button>
          <button v-if="mode === 'success'" class="push-onboarding-primary" @click="closePrompt">
            完成
          </button>
          <button v-else-if="mode === 'install'" class="push-onboarding-primary" @click="dismiss">
            我知道了
          </button>
          <button
            v-else-if="permission === 'denied' || !ready"
            class="push-onboarding-primary"
            :disabled="busy"
            @click="recheck"
          >
            {{ busy ? '正在检测…' : '重新检测' }}
          </button>
          <button v-else class="push-onboarding-primary" :disabled="busy" @click="enable">
            {{ busy ? '正在开启…' : error ? '再次开启' : '立即开启' }}
          </button>
        </div>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup>
import { computed, ref, onMounted, onBeforeUnmount, nextTick, useId } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { pushCapability, syncDevice, enableDevice, isPushPrepared } from '../utils/webPush'

const props = defineProps({ userId: [String, Number] })
const router = useRouter()
const titleId = 'push-onboarding-' + useId()
const dialog = ref(null),
  show = ref(false),
  busy = ref(false),
  ready = ref(false),
  permission = ref('default'),
  mode = ref('enable'),
  error = ref(''),
  publicKey = ref('')
const heading = computed(
  () =>
    ({ enable: '为当前设备开启通知', install: '将通知带到主屏幕', success: '当前设备已开启通知' })[
      mode.value
    ],
)
// A UI-only fingerprint distinguishes logins without copying a login token into sessionStorage.
const sessionStamp = String(
  [
    ...(localStorage.getItem('auth_token') ||
      localStorage.getItem('auth_expires_at') ||
      'current-session'),
  ].reduce((hash, char) => Math.imul(hash ^ char.charCodeAt(0), 16777619), 2166136261) >>> 0,
)
const deferKey = `push_onboarding_${props.userId}`
let alive = true,
  generation = 0,
  successTimer,
  controller
const accountCurrent = () =>
  alive && String(localStorage.getItem('user_id') || '') === String(props.userId)
function deferred() {
  try {
    return sessionStorage.getItem(deferKey) === sessionStamp
  } catch {
    return false
  }
}
function closePrompt() {
  generation++
  show.value = false
  dialog.value?.close()
  clearTimeout(successTimer)
}
function dismiss() {
  try {
    sessionStorage.setItem(deferKey, sessionStamp)
  } catch {
    /* Session deferral is optional. */
  }
  closePrompt()
}
function openCenter() {
  dismiss()
  router.push('/notifications')
}
async function present() {
  await nextTick()
  if (!accountCurrent() || !show.value || document.hidden || !dialog.value || dialog.value.open)
    return
  // A business dialog already in use takes precedence over this login reminder.
  if (document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return
  dialog.value.showModal()
}
async function inspect(force = false) {
  const serial = ++generation
  controller?.abort()
  controller = new AbortController()
  const capability = pushCapability()
  const current = () => accountCurrent() && serial === generation
  const [settings, device] = await Promise.allSettled([
    axios.get('/api/notifications/settings', { timeout: 10000, signal: controller.signal }),
    syncDevice({ isCurrent: current }),
  ])
  if (!current()) return
  if (settings.status !== 'fulfilled') {
    if (force) {
      ready.value = false
      error.value = '通知配置暂时无法读取，请重试或前往通知中心。'
    }
    return
  }
  const config = settings.value.data
  permission.value = window.Notification?.permission || 'unavailable'
  publicKey.value = config.public_key || ''
  ready.value = isPushPrepared()
  if (!config.enabled || !config.configured || !publicKey.value) {
    if (force) {
      ready.value = false
      error.value = '账号推送已暂停或服务尚未就绪，可在通知中心查看具体状态。'
    }
    return
  }
  if (!force && deferred()) return
  if (capability.code === 'ios_install_required') {
    mode.value = 'install'
  } else {
    if (capability.code !== 'supported') return
    if (permission.value === 'denied' && !force) return
    if (device.status === 'fulfilled' && device.value?.active && permission.value === 'granted') {
      if (force) {
        mode.value = 'success'
        show.value = true
        await present()
      }
      return
    }
    // Unknown server state does not prove that an already-authorized device needs repair.
    if (
      (device.status !== 'fulfilled' || !device.value) &&
      permission.value === 'granted' &&
      !force
    )
      return
    if (!ready.value && !force) return
    mode.value = 'enable'
  }
  show.value = true
  await present()
}
async function enable() {
  if (
    busy.value ||
    !show.value ||
    !accountCurrent() ||
    mode.value !== 'enable' ||
    !ready.value ||
    permission.value === 'denied'
  )
    return
  const serial = ++generation
  const current = () => accountCurrent() && show.value && serial === generation
  busy.value = true
  error.value = ''
  try {
    // Safari needs the original button gesture: no preparation/network await before this call.
    const device = await enableDevice(publicKey.value, { isCurrent: current })
    if (!current()) return
    if (!device?.active) throw new Error('尚未完成设备订阅，请再次开启或到通知中心重试。')
    await axios.put('/api/notifications/preference', { enabled: true }, { timeout: 10000 })
    if (!current()) return
    permission.value = window.Notification?.permission || 'granted'
    mode.value = 'success'
    successTimer = setTimeout(closePrompt, 2500)
  } catch (err) {
    if (current() && err.name !== 'AbortError') {
      permission.value = window.Notification?.permission || 'default'
      error.value =
        err.response?.data?.error || err.message || '未能开启通知，请重试或使用通知中心备用设置。'
    }
  } finally {
    if (alive) busy.value = false
  }
}
async function recheck() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await inspect(true)
  } finally {
    if (alive) busy.value = false
  }
}
onMounted(() => {
  inspect().catch(() => {
    /* Notification setup must not block login or normal business. */
  })
  document.addEventListener('visibilitychange', present)
  document.addEventListener('close', present, true)
})
onBeforeUnmount(() => {
  alive = false
  generation++
  controller?.abort()
  clearTimeout(successTimer)
  dialog.value?.close()
  document.removeEventListener('visibilitychange', present)
  document.removeEventListener('close', present, true)
})
</script>
<style scoped>
.push-onboarding {
  box-sizing: border-box;
  width: min(540px, calc(100vw - 28px));
  max-height: calc(100dvh - 36px);
  overflow-y: auto;
  padding: 0;
  color: #25475f;
  background: #fff;
  border: 1px solid #b6cedd;
  border-radius: 18px;
  box-shadow: 0 22px 80px #102b4540;
}
.push-onboarding::backdrop {
  background: #102b4566;
}
.push-onboarding header {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 25px 24px;
  background: linear-gradient(115deg, #16384f, #246878);
  color: #fff;
}
.push-onboarding-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border: 1px solid #ffffff40;
  border-radius: 13px;
  background: #ffffff13;
}
.push-onboarding header small {
  color: #bbdce5;
  font-size: 12px;
}
.push-onboarding h2 {
  margin: 7px 0 0;
  font-size: 21px;
  font-weight: 650;
}
.push-onboarding button {
  padding: 10px 14px;
  color: #315b76;
  background: #f5f9fc;
  border: 1px solid #c5d8e5;
  border-radius: 9px;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 600;
}
.push-onboarding button:hover:not(:disabled) {
  background: #e7f2f7;
  border-color: #48889d;
}
.push-onboarding button:focus-visible {
  outline: 3px solid #73b5d3;
  outline-offset: 3px;
}
.push-onboarding .push-onboarding-close {
  padding: 5px 10px;
  margin-left: auto;
  background: #ffffff12;
  border-color: #ffffff40;
  color: #fff;
  font-size: 23px;
}
.push-onboarding .push-onboarding-close:hover {
  background: #ffffff25;
}
.push-onboarding-content {
  padding: 22px 24px 18px;
}
.push-onboarding-content > p {
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.85;
}
.push-onboarding-hint {
  border: 1px solid #cee1e9;
  background: #eff7fa;
  border-left: 3px solid #2c8b9a;
  padding: 15px;
  border-radius: 10px;
}
.push-onboarding-hint strong {
  font-size: 14px;
}
.push-onboarding-hint p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.85;
  color: #537286;
}
.push-onboarding-content .push-onboarding-note {
  margin: 16px 0 0;
  font-size: 12px;
  color: #71889a;
}
.push-onboarding-error {
  padding: 12px;
  color: #a24430;
  background: #fff0ec;
  border: 1px solid #edc3b9;
  border-radius: 9px;
}
.push-onboarding-content .push-onboarding-error {
  margin-top: 14px;
}
.push-onboarding-success {
  padding: 13px;
  color: #247056;
  background: #eaf7f0;
  border: 1px solid #bcddcd;
  border-radius: 9px;
}
.push-onboarding footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 24px;
  border-top: 1px solid #dee8ef;
  background: #f8fbfd;
}
.push-onboarding footer > div {
  display: flex;
  gap: 8px;
}
.push-onboarding .push-onboarding-link {
  padding-left: 0;
  padding-right: 0;
  background: transparent;
  border-color: transparent;
  font-weight: 500;
  font-size: 12px;
}
.push-onboarding .push-onboarding-primary {
  background: #246f8d;
  border-color: #246f8d;
  color: #fff;
}
.push-onboarding .push-onboarding-primary:hover:not(:disabled) {
  background: #18566f;
}
.push-onboarding button:disabled {
  opacity: 0.6;
  cursor: progress;
}
.push-install-steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 12px;
}
.push-install-steps li {
  display: flex;
  gap: 12px;
  align-items: center;
  font-size: 14px;
  line-height: 1.7;
}
.push-install-steps b {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  background: #e7f1f6;
  color: #216a82;
  border-radius: 8px;
}
@media (max-width: 560px) {
  .push-onboarding header {
    padding: 20px 18px;
    gap: 10px;
  }
  .push-onboarding-icon {
    width: 38px;
    height: 42px;
  }
  .push-onboarding h2 {
    font-size: 18px;
  }
  .push-onboarding-content {
    padding: 18px;
  }
  .push-onboarding footer {
    padding: 15px 18px;
    flex-direction: column-reverse;
    align-items: stretch;
  }
  .push-onboarding footer > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .push-onboarding footer > div > :only-child {
    grid-column: 1 / -1;
  }
}
</style>
