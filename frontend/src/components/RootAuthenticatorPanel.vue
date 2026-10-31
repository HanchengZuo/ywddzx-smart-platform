<template>
  <section class="authenticator-panel" aria-labelledby="root-authenticator-title">
    <header>
      <div><span class="root-label">ROOT 专属登录方式</span><h3 id="root-authenticator-title">Microsoft Authenticator</h3></div>
      <span class="state" :class="{ enabled }">{{ loading ? '读取中' : enabled ? '已启用' : '未启用' }}</span>
    </header>
    <p>绑定后，登录时填写 root，在原密码框输入手机上的 6 位验证码即可。原有 Passkey 保留，其他账号不受影响。</p>
    <p class="security-note">验证码不是额外的第二步验证，也不具备 Passkey 的抗钓鱼能力。请仅在可信的网站地址输入；绑定、停用及原有高敏操作仍需 Passkey 验证。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="setup" class="setup">
      <img :src="setup.qr_code" alt="仅供 root 本人扫描的 Authenticator 绑定二维码" />
      <div>
        <h4>添加“其他帐户”并扫描二维码</h4>
        <p>在 Microsoft Authenticator 中选择“+ → 其他帐户”。二维码 5 分钟内有效，验证成功前不会启用。请勿分享或截图保存二维码、密钥。</p>
        <details><summary>无法扫码？查看手动输入密钥</summary><code>{{ setup.secret }}</code><p>帐户 root，名称 YWDDZX，6 位、30 秒、SHA-1。</p></details>
        <form @submit.prevent="confirmSetup">
          <label>手机上的 6 位验证码<input v-model="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" :disabled="busy" /></label>
          <div class="actions"><button type="button" :disabled="busy" @click="clearSetup">取消</button><button class="primary" :disabled="busy || !/^[0-9]{6}$/.test(code)">{{ busy ? '正在验证…' : '验证并启用' }}</button></div>
        </form>
      </div>
    </div>
    <div v-else class="actions">
      <button v-if="!enabled" type="button" class="primary" :disabled="loading || busy || unavailable" @click="beginSetup">{{ busy ? '正在进行安全验证…' : '绑定 Microsoft Authenticator' }}</button>
      <button v-else type="button" :disabled="busy || unavailable" @click="disable">{{ busy ? '正在进行安全验证…' : '停用验证码登录' }}</button>
      <button v-if="error && !busy" type="button" @click="load">重新读取状态</button>
    </div>
    <p v-if="unavailable" class="security-note">此设备暂不能使用 Passkey 身份复核，请在已绑定 Passkey 的受信任设备上管理。</p>
  </section>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import axios from 'axios'
import { runPasskeyAuthentication, friendlyPasskeyError, passkeyClientAvailable } from '../utils/passkeyClient'
const emit = defineEmits(['busy', 'session-invalidated'])
const props = defineProps({ externalBusy: Boolean })
const enabled = ref(false), loading = ref(true), busy = ref(false), error = ref(''), setup = ref(null), code = ref('')
const unavailable = computed(() => !passkeyClientAvailable())
const controller = new AbortController()
let active = true
const options = () => ({ signal: controller.signal })
const clearSetup = () => { setup.value = null; code.value = '' }
async function load() {
  loading.value = true
  error.value = ''
  try { const { data } = await axios.get('/api/auth/root-authenticator', options()); if (active) enabled.value = data.enabled }
  catch (err) { if (active) error.value = err.response?.data?.error || '登录方式读取失败，请重试。' }
  finally { if (active) loading.value = false }
}
async function managementAuthorization() {
  const { data } = await axios.post('/api/auth/passkey/reauth/options', {}, options())
  const credential = await runPasskeyAuthentication(data.public_key)
  if (!active) throw new Error('已关闭安全设置。')
  const response = await axios.post('/api/auth/passkey/reauth/verify', { flow_id: data.flow_id, credential }, options())
  return response.data.management_token
}
async function perform(work) {
  if (busy.value || props.externalBusy) return
  busy.value = true; emit('busy', true); error.value = ''
  try { await work() }
  catch (err) { if (active) error.value = friendlyPasskeyError(err, err.response?.data?.error || err.message || '安全操作未完成。') }
  finally { if (active) { busy.value = false; emit('busy', false) } }
}
async function beginSetup() {
  await perform(async () => {
    const management_token = await managementAuthorization()
    const { data } = await axios.post('/api/auth/root-authenticator', { management_token }, options())
    if (active) setup.value = { ...data, management_token }
  })
}
async function confirmSetup() {
  if (!setup.value || !/^[0-9]{6}$/.test(code.value)) return
  await perform(async () => {
    const { data } = await axios.put('/api/auth/root-authenticator', { management_token: setup.value.management_token, setup_id: setup.value.setup_id, code: code.value }, options())
    clearSetup()
    if (active) emit('session-invalidated', data.message)
  })
  code.value = ''
}
async function disable() {
  if (!window.confirm('停用后，root将继续使用Passkey登录。确认停用Microsoft Authenticator？')) return
  await perform(async () => {
    const management_token = await managementAuthorization()
    const { data } = await axios.delete('/api/auth/root-authenticator', { ...options(), data: { management_token } })
    if (active) emit('session-invalidated', data.message)
  })
}
onMounted(load)
onBeforeUnmount(() => { active = false; controller.abort(); clearSetup(); emit('busy', false) })
</script>

<style scoped>
.authenticator-panel { margin-top: 18px; padding: 20px; border: 1px solid #cbdde7; border-radius: 18px; background: #fff; color: #24465e; }
header { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.root-label { color: #17665f; font-size: 12px; font-weight: 600; }
h3 { margin: 6px 0; font-size: 20px; } h4 { margin: 0; } p { font-size: 14px; line-height: 1.7; }
.state { flex-shrink: 0; border-radius: 7px; background: #eef3f7; padding: 6px 10px; font-size: 13px; }
.state.enabled { background: #d8f0ea; color: #17665f; }
.security-note { color: #60788a; } .error { color: #ae3027; background: #fff1ef; padding: 12px; border-radius: 9px; }
.setup { display: grid; grid-template-columns: 220px minmax(0,1fr); gap: 22px; margin-top: 20px; }
.setup img { width: 220px; max-width: 100%; height: auto; align-self: start; }
details { margin: 12px 0; } summary { cursor: pointer; font-size: 14px; } code { display: block; margin-top: 10px; overflow-wrap: anywhere; font-size: 15px; }
label { display: grid; gap: 8px; font-size: 14px; } input { width: 100%; box-sizing: border-box; border: 1px solid #abc3d3; border-radius: 9px; padding: 10px; font: inherit; letter-spacing: .25em; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
button { border: 1px solid #abc3d3; border-radius: 9px; padding: 10px 14px; color: #294b65; background: #f2f5f8; cursor: pointer; font: inherit; font-size: 14px; font-weight: 600; }
button.primary { background: #17665f; border-color: #17665f; color: #fff; } button:disabled { opacity: .5; cursor: not-allowed; }
@media(max-width:650px) { .setup { grid-template-columns: 1fr; } .setup img { justify-self: center; } .authenticator-panel { padding: 16px; } header { align-items: start; } }
</style>
