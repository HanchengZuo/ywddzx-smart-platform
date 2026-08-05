<template>
  <div v-if="visible" class="passkey-modal-backdrop" role="dialog" aria-modal="true">
    <div class="passkey-modal-frame">
      <button class="passkey-modal-close" type="button" aria-label="关闭" :disabled="busy" @click="emit('close')">×</button>
      <section class="passkey-modal-card">
      <header class="passkey-modal-head">
        <div class="passkey-shield"><span></span></div>
        <div>
          <span>登录安全</span>
          <h2>我的 Passkey</h2>
          <p>使用指纹、面容、设备解锁或安全密钥登录，系统只保存公钥。</p>
        </div>
      </header>

      <div v-if="!clientAvailable" class="passkey-alert danger">{{ unavailableMessage }}</div>
      <div v-else-if="backupRecommended" class="passkey-alert warning">
        root账号建议至少绑定两个Passkey，避免单个设备遗失后无法登录。
      </div>
      <div v-if="message.text" :class="['passkey-alert', message.type]">{{ message.text }}</div>

      <div class="passkey-summary">
        <div><span>已绑定</span><strong>{{ passkeys.length }}</strong><small>个Passkey</small></div>
        <div><span>登录规则</span><strong>{{ passkeyOnly ? '仅Passkey' : '双方式' }}</strong><small>{{ passkeyOnly ? '密码登录已关闭' : '密码或Passkey' }}</small></div>
        <div><span>设备保护</span><strong>本机验证</strong><small>生物识别或设备密码</small></div>
      </div>

      <section class="passkey-add-panel">
        <div>
          <span>添加新设备</span>
          <h3>绑定一个新的Passkey</h3>
          <p>名称仅用于区分设备，例如“办公电脑”或“手机”。</p>
        </div>
        <div class="passkey-add-form">
          <label>
            <span>Passkey名称</span>
            <input v-model.trim="credentialName" maxlength="80" placeholder="例如：我的手机" />
          </label>
          <label v-if="requiresPasswordForChanges">
            <span>当前账号密码</span>
            <input v-model="currentPassword" type="password" autocomplete="current-password"
              placeholder="绑定前验证当前密码" />
          </label>
          <button class="passkey-primary-button" type="button" :disabled="busy || !clientAvailable" @click="addPasskey">
            {{ busyAction === 'add' ? '正在调用设备验证...' : '绑定新Passkey' }}
          </button>
        </div>
      </section>

      <section class="passkey-list-section">
        <div class="passkey-list-heading">
          <div><span>已绑定设备</span><strong>{{ passkeys.length ? '可随时改名或移除' : '尚未绑定Passkey' }}</strong></div>
          <button type="button" :disabled="loading || busy" @click="loadPasskeys">刷新</button>
        </div>

        <div v-if="loading" class="passkey-empty"><span class="passkey-spinner"></span>正在读取Passkey</div>
        <div v-else-if="!passkeys.length" class="passkey-empty">绑定后即可在登录页使用Passkey进入系统。</div>
        <div v-else class="passkey-list">
          <article v-for="item in passkeys" :key="item.id">
            <div class="passkey-device-icon"><span></span></div>
            <div class="passkey-device-main">
              <input v-model.trim="item.credential_name" maxlength="80" aria-label="Passkey名称" />
              <div>
                <span>{{ deviceTypeLabel(item) }}</span>
                <span>{{ item.backed_up ? '已同步备份' : '本机凭据' }}</span>
              </div>
              <small>绑定 {{ item.created_at }} · 最近使用 {{ item.last_used_at }}</small>
            </div>
            <div class="passkey-device-actions">
              <button type="button" :disabled="busy" @click="renamePasskey(item)">保存名称</button>
              <button class="danger" type="button" :disabled="busy || (passkeyOnly && passkeys.length <= 1)"
                :title="passkeyOnly && passkeys.length <= 1 ? 'root账号不能删除最后一个Passkey' : ''"
                @click="removePasskey(item)">删除</button>
            </div>
          </article>
        </div>
      </section>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import axios from 'axios'
import {
  friendlyPasskeyError,
  getPasskeyUnavailableMessage,
  passkeyClientAvailable,
  runPasskeyAuthentication,
  runPasskeyRegistration
} from '../utils/passkeyClient'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'session-invalidated'])
const passkeys = ref([])
const loading = ref(false)
const busyAction = ref('')
const credentialName = ref('')
const currentPassword = ref('')
const passkeyOnly = ref(false)
const requiresPasswordForChanges = ref(true)
const backupRecommended = ref(false)
const message = reactive({ text: '', type: 'success' })
const clientAvailable = computed(() => passkeyClientAvailable())
const unavailableMessage = computed(() => getPasskeyUnavailableMessage())
const busy = computed(() => Boolean(busyAction.value))

const setMessage = (text, type = 'success') => Object.assign(message, { text, type })
const deviceTypeLabel = (item) => item.device_type === 'multi_device' ? '多设备Passkey' : '单设备Passkey'

const loadPasskeys = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/auth/passkeys')
    passkeys.value = (response.data.items || []).map((item) => ({ ...item }))
    passkeyOnly.value = Boolean(response.data.passkey_only)
    requiresPasswordForChanges.value = Boolean(response.data.requires_password_for_changes)
    backupRecommended.value = Boolean(response.data.backup_recommended)
  } catch (error) {
    setMessage(error?.response?.data?.error || 'Passkey信息读取失败。', 'danger')
  } finally {
    loading.value = false
  }
}

const getManagementAuthorization = async () => {
  if (requiresPasswordForChanges.value) {
    if (!currentPassword.value) throw new Error('请先填写当前账号密码。')
    return { current_password: currentPassword.value }
  }
  const optionsResponse = await axios.post('/api/auth/passkey/reauth/options')
  const credential = await runPasskeyAuthentication(optionsResponse.data.public_key)
  const verifyResponse = await axios.post('/api/auth/passkey/reauth/verify', {
    flow_id: optionsResponse.data.flow_id,
    credential
  })
  return { management_token: verifyResponse.data.management_token }
}

const addPasskey = async () => {
  setMessage('')
  if (!credentialName.value) {
    setMessage('请先填写Passkey名称。', 'danger')
    return
  }
  busyAction.value = 'add'
  try {
    const authorization = await getManagementAuthorization()
    const optionsResponse = await axios.post('/api/auth/passkeys/registration/options', authorization)
    const credential = await runPasskeyRegistration(optionsResponse.data.public_key)
    const verifyResponse = await axios.post('/api/auth/passkeys/registration/verify', {
      flow_id: optionsResponse.data.flow_id,
      credential,
      credential_name: credentialName.value
    })
    if (verifyResponse.data.session_invalidated) {
      emit('session-invalidated', verifyResponse.data.message)
      return
    }
    credentialName.value = ''
    currentPassword.value = ''
    setMessage(verifyResponse.data.message || 'Passkey绑定成功。')
    await loadPasskeys()
  } catch (error) {
    setMessage(friendlyPasskeyError(error, error?.message || 'Passkey绑定失败。'), 'danger')
  } finally {
    busyAction.value = ''
  }
}

const renamePasskey = async (item) => {
  if (!item.credential_name) {
    setMessage('Passkey名称不能为空。', 'danger')
    return
  }
  busyAction.value = `rename-${item.id}`
  try {
    const response = await axios.patch(`/api/auth/passkeys/${item.id}`, {
      credential_name: item.credential_name
    })
    setMessage(response.data.message || 'Passkey名称已更新。')
  } catch (error) {
    setMessage(friendlyPasskeyError(error, 'Passkey名称更新失败。'), 'danger')
  } finally {
    busyAction.value = ''
  }
}

const removePasskey = async (item) => {
  if (!window.confirm(`确认删除Passkey【${item.credential_name}】吗？删除后该设备将不能再用于登录。`)) return
  busyAction.value = `delete-${item.id}`
  try {
    const authorization = await getManagementAuthorization()
    const response = await axios.delete(`/api/auth/passkeys/${item.id}`, { data: authorization })
    if (response.data.session_invalidated) {
      emit('session-invalidated', response.data.message)
      return
    }
    setMessage(response.data.message || 'Passkey已删除。')
    await loadPasskeys()
  } catch (error) {
    setMessage(friendlyPasskeyError(error, error?.message || 'Passkey删除失败。'), 'danger')
  } finally {
    busyAction.value = ''
  }
}

watch(() => props.visible, (visible) => {
  if (!visible) return
  credentialName.value = ''
  currentPassword.value = ''
  setMessage('')
  loadPasskeys()
})
</script>

<style scoped>
.passkey-modal-backdrop{position:fixed;inset:0;z-index:1450;display:grid;place-items:center;padding:24px;background:rgba(10,22,36,.62);backdrop-filter:blur(7px)}
.passkey-modal-frame{position:relative;width:min(900px,100%);max-height:calc(100dvh - 48px)}
.passkey-modal-card{width:100%;max-height:calc(100dvh - 48px);overflow-y:auto;box-sizing:border-box;padding:28px;border:1px solid rgba(255,255,255,.5);border-radius:27px;background:#f7fafc;box-shadow:0 30px 100px rgba(15,23,42,.36);color:#182235}
.passkey-modal-close{position:absolute;z-index:3;right:-17px;top:-17px;width:50px;height:50px;border:1px solid rgba(248,113,113,.42);border-radius:50%;background:rgba(254,226,226,.84);color:#dc2626;font-size:33px;font-weight:950;line-height:1;box-shadow:0 16px 34px rgba(185,28,28,.18);backdrop-filter:blur(12px)}
.passkey-modal-head{display:flex;align-items:center;gap:16px;padding-right:52px;margin-bottom:19px}.passkey-modal-head>div:last-child{min-width:0}.passkey-modal-head span{color:#0f766e;font-size:12px;font-weight:900;letter-spacing:.14em}.passkey-modal-head h2{margin:4px 0;font-size:26px}.passkey-modal-head p{margin:0;color:#697689;line-height:1.55}.passkey-shield{width:58px;height:66px;flex:0 0 auto;display:grid;place-items:center;clip-path:polygon(50% 0,94% 18%,85% 73%,50% 100%,15% 73%,6% 18%);background:linear-gradient(145deg,#0f766e,#164a72)}.passkey-shield span{width:18px;height:24px;border:3px solid #fff;border-radius:10px 10px 6px 6px;box-sizing:border-box;position:relative}.passkey-shield span:before{content:"";position:absolute;left:50%;top:-11px;width:11px;height:11px;border:3px solid #fff;border-bottom:0;border-radius:10px 10px 0 0;transform:translateX(-50%)}
.passkey-alert{margin:10px 0;padding:12px 14px;border-radius:14px;background:#e6f6f1;color:#08765a;font-size:13px;line-height:1.55}.passkey-alert.warning{background:#fff4d9;color:#8b5d09}.passkey-alert.danger{background:#fde9e7;color:#aa342f}
.passkey-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0}.passkey-summary>div{padding:15px;border:1px solid #dce6ec;border-radius:17px;background:#fff;display:grid;gap:3px}.passkey-summary span,.passkey-summary small{color:#778597;font-size:11px}.passkey-summary strong{font-size:19px}
.passkey-add-panel{display:grid;grid-template-columns:minmax(210px,.75fr) minmax(350px,1.25fr);gap:20px;padding:19px;border-radius:20px;background:linear-gradient(135deg,#173e60,#0f766e);color:#fff}.passkey-add-panel>div:first-child>span{font-size:11px;font-weight:900;letter-spacing:.13em;color:#a8eee1}.passkey-add-panel h3{margin:5px 0;font-size:20px}.passkey-add-panel p{margin:0;color:#d4e5eb;font-size:12px;line-height:1.55}.passkey-add-form{display:grid;grid-template-columns:1fr 1fr;gap:10px}.passkey-add-form label{display:grid;gap:6px}.passkey-add-form label span{font-size:11px;color:#d9ebee;font-weight:800}.passkey-add-form input{width:100%;min-height:42px;box-sizing:border-box;border:1px solid rgba(255,255,255,.28);border-radius:12px;padding:10px 12px;background:rgba(255,255,255,.12);color:#fff;outline:0}.passkey-add-form input::placeholder{color:#bdd0d8}.passkey-primary-button{grid-column:1/-1;min-height:43px;border:0;border-radius:12px;background:#fff;color:#125f58;font-weight:900}.passkey-primary-button:disabled{opacity:.62}
.passkey-list-section{margin-top:18px;padding:19px;border:1px solid #dee7ed;border-radius:20px;background:#fff}.passkey-list-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.passkey-list-heading>div{display:grid;gap:3px}.passkey-list-heading span{font-size:11px;color:#0f766e;font-weight:900}.passkey-list-heading strong{font-size:15px}.passkey-list-heading button{border:1px solid #d5e0e7;border-radius:10px;padding:7px 11px;background:#f8fafc;color:#536579}.passkey-list{display:grid;gap:9px}.passkey-list article{display:grid;grid-template-columns:45px 1fr auto;align-items:center;gap:13px;padding:13px;border:1px solid #e2e9ee;border-radius:15px;background:#fbfdfe}.passkey-device-icon{width:43px;height:43px;display:grid;place-items:center;border-radius:14px;background:#e6f4f1}.passkey-device-icon span{width:18px;height:10px;border:3px solid #0f766e;border-radius:999px;position:relative}.passkey-device-icon span:after{content:"";position:absolute;left:15px;top:50%;width:12px;height:3px;background:#0f766e;transform:translateY(-50%)}.passkey-device-main{min-width:0;display:grid;gap:5px}.passkey-device-main input{min-width:0;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid transparent;background:transparent;padding:3px 0;color:#172033;font-weight:900}.passkey-device-main input:focus{outline:0;border-bottom-color:#0f766e}.passkey-device-main>div{display:flex;gap:6px;flex-wrap:wrap}.passkey-device-main>div span{padding:3px 7px;border-radius:999px;background:#edf3f6;color:#607083;font-size:10px}.passkey-device-main small{color:#8290a0;font-size:10px}.passkey-device-actions{display:flex;gap:6px}.passkey-device-actions button{border:1px solid #cad8e1;border-radius:9px;padding:7px 9px;background:#fff;color:#315a72;white-space:nowrap}.passkey-device-actions button.danger{border-color:#edc0bc;color:#ac3b36}.passkey-device-actions button:disabled{opacity:.45}.passkey-empty{min-height:100px;display:flex;align-items:center;justify-content:center;gap:9px;color:#778597}.passkey-spinner{width:20px;height:20px;border:3px solid #d8e3e8;border-top-color:#0f766e;border-radius:50%;animation:passkeySpin .8s linear infinite}@keyframes passkeySpin{to{transform:rotate(360deg)}}
@media(max-width:720px){.passkey-modal-backdrop{padding:12px;align-items:end}.passkey-modal-frame{width:100%;max-height:calc(100dvh - 24px)}.passkey-modal-card{width:100%;max-height:calc(100dvh - 24px);padding:20px 15px 24px;border-radius:24px}.passkey-modal-close{right:7px;top:7px;width:46px;height:46px;font-size:30px}.passkey-modal-head{align-items:flex-start;padding-right:44px}.passkey-modal-head h2{font-size:22px}.passkey-shield{width:48px;height:55px}.passkey-summary{grid-template-columns:1fr}.passkey-add-panel{grid-template-columns:1fr;padding:16px}.passkey-add-form{grid-template-columns:1fr}.passkey-primary-button{grid-column:auto}.passkey-list-section{padding:14px}.passkey-list article{grid-template-columns:42px 1fr}.passkey-device-actions{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr}.passkey-device-actions button{min-height:39px}}
</style>
