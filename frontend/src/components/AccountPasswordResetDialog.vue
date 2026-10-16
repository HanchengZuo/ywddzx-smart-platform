<template>
  <Teleport to="body">
    <dialog ref="dialog" class="password-reset-dialog" aria-labelledby="password-reset-title"
      @cancel.prevent="close" @click="closeOnBackdrop">
      <div class="reset-dialog-body">
        <header>
          <div>
            <p class="reset-eyebrow">账号安全</p>
            <h3 id="password-reset-title">{{ credential ? '初始密码已生成' : '重置用户密码' }}</h3>
          </div>
          <button type="button" class="reset-close" aria-label="关闭" :disabled="loading" @click="close">×</button>
        </header>
        <div class="reset-account">
          <strong>{{ target?.username }}</strong>
          <span>{{ target?.real_name || '系统用户' }}</span>
        </div>
        <template v-if="credential">
          <p class="reset-notice">此密码仅在本次显示，请复制并安全告知用户。用户登录后必须修改密码。</p>
          <label class="reset-credential">
            <span>随机初始密码</span>
            <input ref="passwordInput" :value="credential.password" type="text" readonly autocomplete="off"
              spellcheck="false" aria-label="随机初始密码" @focus="$event.target.select()" />
          </label>
          <p class="reset-copy-status" role="status">{{ copyStatus }}</p>
        </template>
        <p v-else class="reset-notice">
          将生成符合当前安全策略的随机初始密码，原登录会话同时失效。用户下次登录后必须立即修改密码，账号角色和权限不受影响。
        </p>
        <p v-if="error" class="reset-error" role="alert">{{ error }}</p>
        <footer>
          <button class="btn btn-secondary" type="button" :disabled="loading" @click="close">
            {{ credential ? '完成并关闭' : '取消' }}
          </button>
          <button v-if="credential" class="btn btn-primary" type="button" @click="copyCredential">复制登录凭据</button>
          <button v-else class="btn btn-primary" type="button" :disabled="loading" @click="$emit('confirm')">
            {{ loading ? '正在重置...' : '确认重置密码' }}
          </button>
        </footer>
      </div>
    </dialog>
  </Teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  loading: Boolean,
  target: { type: Object, default: null },
  credential: { type: Object, default: null },
  error: { type: String, default: '' }
})
const emit = defineEmits(['close', 'confirm'])
const dialog = ref(null)
const passwordInput = ref(null)
const copyStatus = ref('')
const close = () => { if (!props.loading) emit('close') }
const closeOnBackdrop = (event) => {
  if (event.target !== dialog.value) return
  const bounds = dialog.value.getBoundingClientRect()
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close()
}
const copyCredential = async () => {
  try {
    await navigator.clipboard.writeText(`账号：${props.credential.username}\n初始密码：${props.credential.password}`)
    copyStatus.value = '已复制，请通过安全渠道告知用户。'
  } catch {
    passwordInput.value?.focus()
    passwordInput.value?.select()
    copyStatus.value = '无法自动复制，已选中密码，请手动复制。'
  }
}
watch(() => props.visible, async (visible) => {
  copyStatus.value = ''
  await nextTick()
  if (visible && !dialog.value?.open) dialog.value?.showModal()
  if (!visible) dialog.value?.close()
}, { immediate: true })
onBeforeUnmount(() => dialog.value?.close())
</script>

<style scoped>
.password-reset-dialog { width: min(480px, calc(100vw - 28px)); max-height: calc(100dvh - 28px); overflow: auto; margin: auto; padding: 0; border: 1px solid #dbe4ee; border-radius: 20px; color: #0f172a; box-shadow: 0 28px 80px #0f172a33; }
.password-reset-dialog::backdrop { background: #0f172a80; backdrop-filter: blur(4px); }
.reset-dialog-body { padding: 24px; background: linear-gradient(160deg, #f5f9ff, #fff 40%); }
header, footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.reset-eyebrow { margin: 0 0 5px; color: #2563eb; font-size: 12px; font-weight: 800; }
h3 { margin: 0; font-size: 20px; }
.reset-close { width: 34px; height: 34px; border: 0; border-radius: 10px; background: #eaf0f7; color: #475569; font-size: 24px; cursor: pointer; }
.reset-account { display: flex; align-items: baseline; flex-wrap: wrap; gap: 10px; margin: 22px 0 16px; padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; overflow-wrap: anywhere; }
.reset-account span { color: #64748b; font-size: 13px; }
.reset-notice { color: #475569; font-size: 13px; line-height: 1.8; }
.reset-credential { display: grid; gap: 8px; margin-top: 16px; font-size: 12px; color: #475569; }
.reset-credential input { box-sizing: border-box; min-width: 0; width: 100%; padding: 13px; border: 1px solid #93c5fd; border-radius: 10px; background: #eff6ff; color: #1e3a8a; font-family: monospace; font-size: 16px; }
.reset-copy-status { margin: 8px 0 0; color: #2563eb; font-size: 12px; }
.reset-error { color: #b91c1c; font-size: 13px; line-height: 1.6; }
footer { justify-content: flex-end; flex-wrap: wrap; margin-top: 22px; padding-top: 16px; border-top: 1px solid #e2e8f0; }
.btn { min-height: 38px; padding: 9px 14px; border: 1px solid transparent; border-radius: 10px; font: inherit; font-size: 13px; font-weight: 700; cursor: pointer; }
.btn-primary { background: #2563eb; color: #fff; }
.btn-secondary { border-color: #d7e0ea; background: #fff; color: #475569; }
button:disabled { opacity: .55; cursor: not-allowed; }
button:focus-visible, input:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
@media (max-width: 520px) { .reset-dialog-body { padding: 18px; } footer .btn { flex: 1; } }
</style>
