<template>
  <div v-if="visible" class="account-switcher-mask" role="dialog" aria-modal="true" aria-label="Root账号切换" @click.self="emit('close')">
    <section class="account-switcher-panel">
      <header class="account-switcher-head">
        <div>
          <span class="account-switcher-eyebrow">ROOT ACCOUNT ACCESS</span>
          <h2>切换登录账号</h2>
          <p>切换后将完全按目标账号的权限、站点和数据范围进入系统。</p>
        </div>
        <button class="account-switcher-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
      </header>

      <div v-if="impersonating" class="account-switcher-active">
        <div>
          <span>当前状态</span>
          <strong>Root 正在代入账号 {{ currentDisplayName }}</strong>
        </div>
        <button type="button" :disabled="busy" @click="returnToRoot">
          {{ returning ? '正在返回...' : '返回 Root' }}
        </button>
      </div>

      <div class="account-switcher-toolbar">
        <label class="account-switcher-search">
          <span>搜</span>
          <input v-model.trim="keyword" type="search" placeholder="搜索姓名、用户名、站点或片区" />
        </label>
        <div class="account-switcher-summary">
          <span>可选账号</span>
          <strong>{{ filteredTotal }}</strong>
        </div>
      </div>

      <nav v-if="groups.length" class="account-switcher-roles" aria-label="按角色筛选">
        <button type="button" :class="{ active: selectedRole === '' }" @click="selectedRole = ''">
          全部 <span>{{ total }}</span>
        </button>
        <button v-for="group in groups" :key="group.role" type="button"
          :class="{ active: selectedRole === group.role }" @click="selectedRole = group.role">
          {{ group.role_label }} <span>{{ group.count }}</span>
        </button>
      </nav>

      <div v-if="errorMessage" class="account-switcher-message error">{{ errorMessage }}</div>
      <div v-if="loading" class="account-switcher-loading">
        <span></span>
        <strong>正在读取账号目录</strong>
      </div>
      <div v-else-if="!filteredGroups.length" class="account-switcher-empty">没有找到匹配的账号。</div>
      <div v-else class="account-switcher-groups">
        <section v-for="group in filteredGroups" :key="group.role" class="account-role-group">
          <header>
            <div>
              <span class="account-role-mark">{{ roleMark(group.role_label) }}</span>
              <strong>{{ group.role_label }}</strong>
            </div>
            <em>{{ group.accounts.length }} 个账号</em>
          </header>
          <div class="account-role-grid">
            <article v-for="account in group.accounts" :key="account.id" class="account-switch-card"
              :class="{ current: String(account.id) === String(currentUserId), disabled: account.account_status !== 'active' }">
              <div class="account-switch-avatar">{{ account.display_name.slice(0, 1) }}</div>
              <div class="account-switch-main">
                <div>
                  <strong>{{ account.display_name }}</strong>
                  <span v-if="String(account.id) === String(currentUserId)">当前账号</span>
                  <span v-else-if="account.account_status !== 'active'" class="paused">已暂停</span>
                </div>
                <p>@{{ account.username }}</p>
                <small>{{ accountLocation(account) }}</small>
              </div>
              <button type="button"
                :disabled="busy || account.account_status !== 'active' || String(account.id) === String(currentUserId)"
                @click="switchTo(account)">
                {{ switchingId === account.id ? '切换中...' : '进入账号' }}
              </button>
            </article>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  visible: { type: Boolean, default: false },
  currentUserId: { type: [String, Number], default: '' },
  currentDisplayName: { type: String, default: '' },
  impersonating: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'session-changed'])

const loading = ref(false)
const switchingId = ref(null)
const returning = ref(false)
const errorMessage = ref('')
const keyword = ref('')
const selectedRole = ref('')
const groups = ref([])
const total = ref(0)
const busy = computed(() => Boolean(switchingId.value) || returning.value)

const normalizedKeyword = computed(() => keyword.value.toLocaleLowerCase('zh-CN'))
const filteredGroups = computed(() => groups.value
  .filter((group) => !selectedRole.value || group.role === selectedRole.value)
  .map((group) => ({
    ...group,
    accounts: group.accounts.filter((account) => {
      if (!normalizedKeyword.value) return true
      return [
        account.display_name,
        account.username,
        account.station_name,
        account.region,
        account.role_label
      ].some((value) => String(value || '').toLocaleLowerCase('zh-CN').includes(normalizedKeyword.value))
    })
  }))
  .filter((group) => group.accounts.length))
const filteredTotal = computed(() => filteredGroups.value.reduce((sum, group) => sum + group.accounts.length, 0))

const roleMark = (label) => String(label || '账').slice(0, 1)
const accountLocation = (account) => [account.region, account.station_name].filter(Boolean).join(' · ') || '未绑定站点'

const loadAccounts = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await axios.get('/api/auth/impersonation/accounts')
    groups.value = response.data?.groups || []
    total.value = Number(response.data?.total || 0)
  } catch (error) {
    groups.value = []
    total.value = 0
    errorMessage.value = error?.response?.data?.error || '账号目录读取失败。'
  } finally {
    loading.value = false
  }
}

const switchTo = async (account) => {
  if (busy.value || account.account_status !== 'active') return
  switchingId.value = account.id
  errorMessage.value = ''
  try {
    const response = await axios.post('/api/auth/impersonation/switch', {
      target_user_id: account.id
    })
    emit('session-changed', response.data)
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || '账号切换失败。'
  } finally {
    switchingId.value = null
  }
}

const returnToRoot = async () => {
  if (busy.value) return
  returning.value = true
  errorMessage.value = ''
  try {
    const response = await axios.post('/api/auth/impersonation/exit')
    emit('session-changed', response.data)
  } catch (error) {
    errorMessage.value = error?.response?.data?.error || '返回 Root 失败。'
  } finally {
    returning.value = false
  }
}

watch(() => props.visible, (visible) => {
  if (!visible) return
  keyword.value = ''
  selectedRole.value = ''
  loadAccounts()
})
</script>

<style scoped>
.account-switcher-mask {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(8, 17, 31, 0.58);
  backdrop-filter: blur(10px);
}

.account-switcher-panel {
  width: min(1080px, 100%);
  max-height: min(820px, calc(100dvh - 48px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.84);
  border-radius: 28px;
  background:
    radial-gradient(circle at 92% 2%, rgba(14, 116, 144, 0.13), transparent 30%),
    #f8fafc;
  box-shadow: 0 36px 100px rgba(8, 17, 31, 0.34);
}

.account-switcher-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px 20px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e2e8f0;
}

.account-switcher-eyebrow {
  color: #0e7490;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 1.8px;
}

.account-switcher-head h2 {
  margin: 7px 0 0;
  color: #0f172a;
  font-size: 25px;
  letter-spacing: -0.5px;
}

.account-switcher-head p {
  margin: 7px 0 0;
  color: #64748b;
  font-size: 13px;
}

.account-switcher-close {
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #fff;
  color: #475569;
  font-size: 25px;
  line-height: 1;
  cursor: pointer;
}

.account-switcher-active {
  margin: 18px 28px 0;
  padding: 13px 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border: 1px solid rgba(217, 119, 6, 0.25);
  border-radius: 17px;
  background: linear-gradient(135deg, #fffbeb, #fff7ed);
}

.account-switcher-active div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.account-switcher-active span {
  color: #b45309;
  font-size: 11px;
  font-weight: 900;
}

.account-switcher-active strong {
  color: #7c2d12;
  font-size: 14px;
}

.account-switcher-active button {
  min-height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 11px;
  background: #9a3412;
  color: #fff;
  font-weight: 900;
  cursor: pointer;
}

.account-switcher-toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 28px 12px;
}

.account-switcher-search {
  min-width: 0;
  flex: 1;
  height: 44px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #fff;
}

.account-switcher-search span {
  width: 23px;
  height: 23px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 12px;
  font-weight: 900;
}

.account-switcher-search input {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: #0f172a;
  font-size: 14px;
}

.account-switcher-summary {
  height: 44px;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 14px;
  border-radius: 14px;
  background: #0f172a;
  color: #fff;
}

.account-switcher-summary span {
  color: #cbd5e1;
  font-size: 11px;
}

.account-switcher-summary strong {
  font-size: 18px;
}

.account-switcher-roles {
  display: flex;
  gap: 8px;
  padding: 0 28px 15px;
  overflow-x: auto;
  scrollbar-width: thin;
}

.account-switcher-roles button {
  min-height: 34px;
  flex: 0 0 auto;
  padding: 0 12px;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.account-switcher-roles button span {
  margin-left: 4px;
  color: #94a3b8;
}

.account-switcher-roles button.active {
  border-color: #0e7490;
  background: #0e7490;
  color: #fff;
}

.account-switcher-roles button.active span {
  color: #cffafe;
}

.account-switcher-groups {
  min-height: 0;
  flex: 1;
  padding: 2px 28px 28px;
  overflow-y: auto;
}

.account-role-group + .account-role-group {
  margin-top: 20px;
}

.account-role-group > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.account-role-group > header div {
  display: flex;
  align-items: center;
  gap: 9px;
}

.account-role-mark {
  width: 29px;
  height: 29px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #cffafe, #dbeafe);
  color: #0e7490;
  font-size: 13px;
  font-weight: 900;
}

.account-role-group > header strong {
  color: #1e293b;
  font-size: 14px;
}

.account-role-group > header em {
  color: #94a3b8;
  font-size: 12px;
  font-style: normal;
}

.account-role-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.account-switch-card {
  min-width: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 13px;
  border: 1px solid #e2e8f0;
  border-radius: 17px;
  background: #fff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.account-switch-card:hover {
  border-color: #a5d8e5;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.07);
  transform: translateY(-1px);
}

.account-switch-card.current {
  border-color: #67e8f9;
  background: #ecfeff;
}

.account-switch-card.disabled {
  opacity: 0.62;
}

.account-switch-avatar {
  width: 39px;
  height: 39px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  background: #e2e8f0;
  color: #334155;
  font-weight: 900;
}

.account-switch-main {
  min-width: 0;
}

.account-switch-main > div {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.account-switch-main strong {
  color: #0f172a;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-switch-main span {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 999px;
  background: #cffafe;
  color: #0e7490;
  font-size: 10px;
  font-weight: 900;
}

.account-switch-main span.paused {
  background: #fee2e2;
  color: #b91c1c;
}

.account-switch-main p,
.account-switch-main small {
  margin: 2px 0 0;
  display: block;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-switch-card > button {
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid #a5d8e5;
  border-radius: 11px;
  background: #f0fdfa;
  color: #0f766e;
  font-size: 11px;
  font-weight: 900;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.account-switcher-loading,
.account-switcher-empty {
  min-height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #64748b;
  font-size: 13px;
}

.account-switcher-loading span {
  width: 20px;
  height: 20px;
  border: 3px solid #cbd5e1;
  border-top-color: #0e7490;
  border-radius: 50%;
  animation: accountSwitcherSpin 0.8s linear infinite;
}

.account-switcher-message {
  margin: 0 28px 12px;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.account-switcher-message.error {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
}

@keyframes accountSwitcherSpin {
  to { transform: rotate(360deg); }
}

@media (max-width: 720px) {
  .account-switcher-mask {
    align-items: end;
    padding: 0;
  }

  .account-switcher-panel {
    max-height: 92dvh;
    border-radius: 25px 25px 0 0;
  }

  .account-switcher-head {
    padding: 20px 18px 16px;
  }

  .account-switcher-head h2 {
    font-size: 22px;
  }

  .account-switcher-head p {
    max-width: 88%;
    line-height: 1.55;
  }

  .account-switcher-active {
    margin: 14px 16px 0;
    align-items: stretch;
    flex-direction: column;
  }

  .account-switcher-toolbar {
    padding: 14px 16px 10px;
  }

  .account-switcher-summary {
    display: none;
  }

  .account-switcher-roles {
    padding: 0 16px 13px;
  }

  .account-switcher-groups {
    padding: 2px 16px 22px;
  }

  .account-role-grid {
    grid-template-columns: 1fr;
  }

  .account-switch-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .account-switch-card > button {
    grid-column: 1 / -1;
    width: 100%;
  }
}
</style>
