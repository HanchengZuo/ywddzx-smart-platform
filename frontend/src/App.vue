<template>
  <div v-if="isLoginPage" class="login-page">
    <div class="login-shell">
      <div class="login-hero">
        <div class="login-badge">业务督导中心</div>
        <h1 class="login-title">业务督导中心数智管理平台</h1>
        <p class="login-subtitle">聚合巡检、考核、培训等业务场景，支撑日常督导闭环管理。</p>
        <div class="login-points">
          <span>巡检闭环</span>
          <span>问题追踪</span>
          <span>过程留痕</span>
        </div>
        <div class="login-hero-footer">
          <div class="login-version">
            <span class="login-version-label">当前版本</span>
            <span class="login-version-value">v{{ appVersion }}</span>
          </div>
        </div>
      </div>

      <form class="login-card" @submit.prevent="handleLogin">
        <div class="login-card-header">
          <h2>账号登录</h2>
          <p>请输入系统账号和密码登录平台</p>
        </div>

        <div class="form-item">
          <label>用户名</label>
          <input v-model.trim="loginForm.username" type="text" placeholder="请输入用户名" />
        </div>

        <div class="form-item">
          <label>密码</label>
          <input v-model="loginForm.password" type="password" placeholder="请输入密码" />
        </div>

        <div v-if="loginError" class="login-error">{{ loginError }}</div>

        <button class="btn btn-primary login-btn" type="submit">登录系统</button>
      </form>
    </div>
  </div>

  <div v-else class="layout" :class="{ 'sidebar-collapsed-layout': sidebarCollapsed }">
    <div v-if="mobileMenuOpen" class="mobile-sidebar-mask" @click="closeMobileMenu"></div>

    <header class="mobile-topbar">
      <button class="mobile-menu-btn" type="button" @click="toggleMobileMenu">☰</button>
      <div class="mobile-topbar-title">{{ currentRole === 'station_manager' ? (authState.stationName || '站点账号') :
        '业务督导中心' }}</div>
      <button class="btn btn-secondary btn-sm mobile-logout-btn" type="button" @click="handleLogout">退出</button>
    </header>

    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed, 'mobile-open': mobileMenuOpen }">
      <div class="sidebar-top">
        <div class="sidebar-brand" v-if="!sidebarCollapsed">
          <div class="logo-mark">{{ currentRole === 'station_manager' ? '站' : '督' }}</div>
          <div class="logo-texts">
            <div class="logo-title">{{ currentRole === 'station_manager' ? (authState.stationName || '站点账号') : '业务督导中心'
              }}</div>
            <div class="logo-subtitle">{{ currentRole === 'station_manager' ? '站点账号' : '数智管理平台' }}</div>
          </div>
        </div>

        <button class="sidebar-toggle sidebar-toggle-inner" type="button" @click="toggleSidebar"
          :title="sidebarCollapsed ? '展开边栏' : '收起边栏'">
          {{ sidebarCollapsed ? '☰' : '‹' }}
        </button>
      </div>

      <div v-if="canViewStationMap" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">地图中心</div>

        <button class="nav-item" :class="{ active: isActive('/inspection/station-map'), collapsed: sidebarCollapsed }"
          type="button" @click="go('/inspection/station-map')" :title="sidebarCollapsed ? '站点地图' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">站点地图</span>
        </button>
      </div>

      <div class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">巡检系统</div>

        <button v-if="canSubmitInspections" class="nav-item"
          :class="{ active: isActive('/inspection/register'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/register')" :title="sidebarCollapsed ? '巡检登记' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">巡检登记</span>
        </button>

        <button v-if="canViewInspectionStandards" class="nav-item"
          :class="{ active: isActive('/inspection/standards'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/standards')" :title="sidebarCollapsed ? '巡检规范库' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">巡检规范库</span>
        </button>

        <button v-if="canViewChecklistOriginals" class="nav-item"
          :class="{ active: isActive('/inspection/checklist-originals'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/checklist-originals')" :title="sidebarCollapsed ? '检查表原件库' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">检查表原件库</span>
        </button>

        <button class="nav-item" :class="{ active: isActive('/inspection/my-issues'), collapsed: sidebarCollapsed }"
          type="button" @click="go('/inspection/my-issues')"
          :title="sidebarCollapsed ? (currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题') : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">{{ currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题' }}</span>
        </button>

        <button v-if="canViewIssues" class="nav-item"
          :class="{ active: isActive('/inspection/issues'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/issues')" :title="sidebarCollapsed ? '巡检问题列表' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">巡检问题列表</span>
        </button>

        <button v-if="canViewRecords" class="nav-item"
          :class="{ active: isActive('/inspection/records'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/records')" :title="sidebarCollapsed ? '巡检记录' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">巡检记录</span>
        </button>

        <button v-if="canViewInspectionPlans" class="nav-item"
          :class="{ active: isActive('/inspection/plan'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/plan')" :title="sidebarCollapsed ? '巡检计划' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">巡检计划</span>
        </button>

        <button v-if="canViewCertificates" class="nav-item"
          :class="{ active: isActive('/inspection/certificates'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/certificates')" :title="sidebarCollapsed ? '证照管理' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">证照管理</span>
        </button>
      </div>

      <div v-if="canViewAssessment" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">考核系统</div>
        <button class="nav-item" :class="{ active: isActive('/assessment'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/assessment')" :title="sidebarCollapsed ? '考核系统' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">考核系统</span>
        </button>
      </div>

      <div v-if="canViewTrainingSection" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">培训系统</div>
        <button v-if="canViewTrainingInternal" class="nav-item"
          :class="{ active: isActive('/training'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/training')" :title="sidebarCollapsed ? '培训系统' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">培训系统</span>
        </button>
        <button v-if="canViewTrainingMaterials" class="nav-item"
          :class="{ active: isActive('/training/materials'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/training/materials')" :title="sidebarCollapsed ? '培训材料库' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">培训材料库</span>
        </button>
      </div>

      <div v-if="currentRole !== 'station_manager'" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">车辆系统</div>
        <button class="nav-item" :class="{ active: isActive('/vehicle'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/vehicle')" :title="sidebarCollapsed ? '车辆管理系统' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">车辆管理系统</span>
        </button>
      </div>

      <div class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">公共功能</div>
        <button class="nav-item" :class="{ active: isActive('/feedback'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/feedback')" :title="sidebarCollapsed ? '系统反馈' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">系统反馈</span>
        </button>
      </div>

      <div v-if="isManagementAdmin" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">管理系统</div>
        <button class="nav-item"
          :class="{ active: isActive('/management/users'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/users')" :title="sidebarCollapsed ? '用户数据管理' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">用户数据管理</span>
        </button>
        <button class="nav-item"
          :class="{ active: isActive('/management/stations'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/stations')" :title="sidebarCollapsed ? '站点数据管理' : ''">
          <span class="nav-item-dot"></span>
          <span v-if="!sidebarCollapsed">站点数据管理</span>
        </button>
      </div>
    </aside>

    <div class="main">
      <header class="header">
        <div class="header-left-block">
          <div class="header-left">
            <div class="header-title">业务督导中心数智管理平台</div>
            <div class="header-desc">统一承载巡检、考核、培训等业务场景</div>
          </div>
        </div>

        <div class="header-user-area">
          <div class="header-user-card">
            <div class="header-user-avatar">{{ currentUsername.slice(0, 1) }}</div>
            <div class="header-user-text">
              <div class="header-user-name">{{ currentUsername }}</div>
              <div class="header-user-meta">
                <span v-if="authState.stationName" class="header-user-station">{{ authState.stationName }}</span>
                <span class="header-user-role">{{ currentRoleLabel }}</span>
              </div>
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" type="button" @click="handleLogout">退出登录</button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'
import appPackage from '../package.json'

const router = useRouter()
const route = useRoute()

const loginForm = reactive({
  username: '',
  password: ''
})

const loginError = ref('')
const sidebarCollapsed = ref(false)
const mobileMenuOpen = ref(false)

const parseStoredPermissions = () => {
  try {
    return JSON.parse(localStorage.getItem('permissions') || '{}')
  } catch (error) {
    return {}
  }
}

const authState = reactive({
  token: localStorage.getItem('auth_token') || '',
  userId: localStorage.getItem('user_id') || '',
  username: localStorage.getItem('username') || '',
  realName: localStorage.getItem('real_name') || '',
  role: localStorage.getItem('user_role') || '',
  phone: localStorage.getItem('phone') || '',
  stationId: localStorage.getItem('station_id') || '',
  stationName: localStorage.getItem('station_name') || '',
  region: localStorage.getItem('region') || '',
  address: localStorage.getItem('address') || '',
  permissions: parseStoredPermissions()
})

const isLoginPage = computed(() => route.path === '/login')
const appVersion = appPackage.version || '0.0.0'
const currentRole = computed(() => authState.role)
const currentUsername = computed(() => authState.realName || authState.username || '未命名用户')
const localPermissions = computed(() => authState.permissions || {})
const isRoot = computed(() => authState.role === 'root')
const isSupervisor = computed(() => authState.role === 'supervisor')
const isStationManager = computed(() => authState.role === 'station_manager')
const isManagementAdmin = computed(() => isRoot.value)
const hasPermissionKey = (key) => authState.role === 'root' || Boolean(localPermissions.value[key])
const canViewStationMap = computed(() => hasPermissionKey('view_station_map'))
const canSubmitInspections = computed(() => hasPermissionKey('submit_inspections'))
const canViewInspectionStandards = computed(() => hasPermissionKey('view_inspection_standards'))
const canViewChecklistOriginals = computed(() => hasPermissionKey('view_checklist_originals'))
const canViewIssues = computed(() => (
  isRoot.value ||
  Boolean(localPermissions.value.view_all_inspection_issues) ||
  Boolean(localPermissions.value.view_own_inspection_issues)
))
const canViewRecords = computed(() => (
  isRoot.value ||
  Boolean(localPermissions.value.view_all_inspection_records) ||
  Boolean(localPermissions.value.view_own_inspection_records)
))
const canViewInspectionPlans = computed(() => hasPermissionKey('view_inspection_plans'))
const canViewCertificates = computed(() => (
  isRoot.value ||
  Boolean(localPermissions.value.view_all_certificates) ||
  Boolean(localPermissions.value.view_own_certificates) ||
  Boolean(localPermissions.value.edit_own_certificates)
))
const canViewAssessment = computed(() => hasPermissionKey('view_assessment'))
const canViewTrainingInternal = computed(() => hasPermissionKey('view_training'))
const canViewTrainingMaterials = computed(() => hasPermissionKey('view_training_materials'))
const canViewTrainingSection = computed(() => canViewTrainingInternal.value || canViewTrainingMaterials.value)
const currentRoleLabel = computed(() => {
  if (authState.role === 'root') return '系统管理员'
  return authState.role === 'supervisor' ? '督导组账号' : '站点账号'
})

const syncAuthState = () => {
  authState.token = localStorage.getItem('auth_token') || ''
  authState.userId = localStorage.getItem('user_id') || ''
  authState.username = localStorage.getItem('username') || ''
  authState.realName = localStorage.getItem('real_name') || ''
  authState.role = localStorage.getItem('user_role') || ''
  authState.phone = localStorage.getItem('phone') || ''
  authState.stationId = localStorage.getItem('station_id') || ''
  authState.stationName = localStorage.getItem('station_name') || ''
  authState.region = localStorage.getItem('region') || ''
  authState.address = localStorage.getItem('address') || ''
  authState.permissions = parseStoredPermissions()
}

watch(
  () => route.path,
  () => {
    syncAuthState()
  },
  { immediate: true }
)

const isActive = (path) => route.path === path

const resolveHomePath = (user) => {
  const role = user?.role || ''
  const permissions = user?.permissions || {}
  if (role === 'station_manager') return '/inspection/my-issues'
  if (role === 'root' || permissions.view_station_map) return '/inspection/station-map'
  if (permissions.submit_inspections) return '/inspection/register'
  if (permissions.view_inspection_standards) return '/inspection/standards'
  if (permissions.view_checklist_originals) return '/inspection/checklist-originals'
  if (permissions.view_all_inspection_issues || permissions.view_own_inspection_issues) return '/inspection/issues'
  if (permissions.view_all_inspection_records || permissions.view_own_inspection_records) return '/inspection/records'
  if (permissions.view_inspection_plans) return '/inspection/plan'
  if (permissions.view_all_certificates || permissions.view_own_certificates || permissions.edit_own_certificates) {
    return '/inspection/certificates'
  }
  if (permissions.view_assessment) return '/assessment'
  if (permissions.view_training) return '/training'
  if (permissions.view_training_materials) return '/training/materials'
  return '/feedback'
}

const go = (path) => {
  if (route.path !== path) {
    router.push(path)
  }
  mobileMenuOpen.value = false
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const toggleMobileMenu = () => {
  mobileMenuOpen.value = !mobileMenuOpen.value
}

const closeMobileMenu = () => {
  mobileMenuOpen.value = false
}

const handleLogin = async () => {
  if (!loginForm.username) {
    loginError.value = '请输入用户名。'
    return
  }

  if (!loginForm.password) {
    loginError.value = '请输入密码。'
    return
  }

  try {
    loginError.value = ''

    const response = await axios.post('/api/login', {
      username: loginForm.username,
      password: loginForm.password
    })

    const user = response.data.user
    const fakeToken = `backend-login-${Date.now()}`

    localStorage.setItem('auth_token', fakeToken)
    localStorage.setItem('user_id', user.id ?? '')
    localStorage.setItem('username', user.username || '')
    localStorage.setItem('real_name', user.real_name || '')
    localStorage.setItem('user_role', user.role || '')
    localStorage.setItem('phone', user.phone || '')
    localStorage.setItem('station_id', user.station_id ?? '')
    localStorage.setItem('station_name', user.station_name || '')
    localStorage.setItem('region', user.region || '')
    localStorage.setItem('address', user.address || '')
    localStorage.setItem('permissions', JSON.stringify(user.permissions || {}))

    syncAuthState()
    loginForm.password = ''
    router.push(resolveHomePath(user))
  } catch (error) {
    const message = error?.response?.data?.error || '登录失败，请稍后重试。'
    loginError.value = message
  }
}

const handleLogout = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('username')
  localStorage.removeItem('real_name')
  localStorage.removeItem('user_role')
  localStorage.removeItem('phone')
  localStorage.removeItem('station_id')
  localStorage.removeItem('station_name')
  localStorage.removeItem('region')
  localStorage.removeItem('address')
  localStorage.removeItem('permissions')
  syncAuthState()
  mobileMenuOpen.value = false
  loginForm.password = ''
  router.push('/login')
}
</script>

<style>
:root {
  --bg-app: #eef3f8;
  --bg-panel: rgba(255, 255, 255, 0.96);
  --bg-panel-soft: #f8fafc;
  --line-color: #d9e2ec;
  --line-soft: #e7edf4;
  --text-main: #0f172a;
  --text-sub: #64748b;
  --text-soft: #94a3b8;
  --brand: #2563eb;
  --brand-hover: #1d4ed8;
  --sidebar-bg: linear-gradient(180deg, #16233c 0%, #101a2c 100%);
  --sidebar-text: rgba(255, 255, 255, 0.9);
  --shadow-card: 0 18px 40px rgba(15, 23, 42, 0.08);
  --shadow-soft: 0 10px 24px rgba(15, 23, 42, 0.06);
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  width: 100%;
  height: 100%;
  margin: 0;
}

body {
  font-family: Arial, 'Microsoft YaHei', sans-serif;
  background: var(--bg-app);
  color: var(--text-main);
}

button,
input,
select,
textarea {
  font: inherit;
}

.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow-y: auto;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 32%),
    radial-gradient(circle at bottom right, rgba(59, 130, 246, 0.12), transparent 26%),
    linear-gradient(180deg, #f7faff 0%, #edf3f8 100%);
}

.login-shell {
  width: 100%;
  max-width: 1120px;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 28px;
  align-items: stretch;
}

.login-hero,
.login-card {
  border: 1px solid rgba(217, 226, 236, 0.9);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow-card);
}

.login-hero {
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 520px;
}

.login-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: var(--brand);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 18px;
}

.login-title {
  margin: 0 0 14px;
  font-size: 42px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: 0.4px;
}

.login-subtitle {
  margin: 0;
  color: var(--text-sub);
  font-size: 16px;
  line-height: 1.8;
  max-width: 560px;
}

.login-points {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 28px;
}

.login-points span {
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid var(--line-soft);
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}

.login-hero-footer {
  margin-top: 28px;
  padding-top: 18px;
  border-top: 1px solid rgba(217, 226, 236, 0.9);
  display: flex;
  align-items: center;
  justify-content: flex-start;
}

.login-card {
  padding: 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.login-card-header {
  margin-bottom: 18px;
}

.login-card-header h2 {
  margin: 0 0 8px;
  font-size: 26px;
}

.login-card-header p {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 18px;
}

.form-item label {
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.form-item input,
.form-item select {
  width: 100%;
  height: 48px;
  border: 1px solid var(--line-color);
  border-radius: 14px;
  padding: 0 14px;
  background: #fff;
  color: var(--text-main);
  transition: all 0.18s ease;
}

.form-item input:focus,
.form-item select:focus,
textarea:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.42);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.login-tips,
.login-error {
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.7;
  margin-bottom: 16px;
}

.login-tips {
  background: #f8fafc;
  border: 1px solid var(--line-soft);
  color: #475569;
}

.login-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}

.layout {
  display: flex;
  width: 100%;
  height: 100vh;
}

.mobile-topbar,
.mobile-sidebar-mask {
  display: none;
}

.sidebar {
  width: 272px;
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
  padding: 14px 12px 18px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  transition: width 0.2s ease, padding 0.2s ease;
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 6px 14px;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 800;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.2);
}

.logo-title {
  font-size: 18px;
  font-weight: 800;
  color: #fff;
}

.logo-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.58);
}

.menu-section {
  margin-top: 14px;
}

.menu-section-title {
  padding: 0 8px;
  margin-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.8px;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 700;
}

.nav-item {
  width: 100%;
  border: none;
  background: transparent;
  color: var(--sidebar-text);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 12px;
  border-radius: 14px;
  cursor: pointer;
  margin-bottom: 6px;
  text-align: left;
  transition: all 0.18s ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.28) 0%, rgba(37, 99, 235, 0.12) 100%);
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(96, 165, 250, 0.18);
}

.nav-item-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.45);
  flex-shrink: 0;
}

.nav-item.active .nav-item-dot {
  background: #60a5fa;
}

.sidebar.collapsed {
  width: 76px;
  padding-left: 10px;
  padding-right: 10px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.nav-item.collapsed {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar-toggle {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  background: rgba(255, 255, 255, 0.12);
}

.header-left-block {
  display: flex;
  align-items: center;
  min-width: 0;
}

.sidebar-collapsed-layout .sidebar {
  width: 76px;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 76px;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line-soft);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 28px;
  flex-shrink: 0;
}

.header-left {
  min-width: 0;
}

.header-title {
  font-size: 24px;
  font-weight: 800;
  color: var(--text-main);
}

.header-desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--text-sub);
}

.header-user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--line-soft);
  min-width: 0;
}

.header-user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  color: #1d4ed8;
  font-weight: 800;
}

.header-user-text {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.header-user-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-wrap: nowrap;
}

.header-user-name {
  font-size: 14px;
  font-weight: 700;
}

.header-user-station {
  font-size: 12px;
  color: #475569;
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-user-role {
  font-size: 12px;
  color: var(--text-sub);
  white-space: nowrap;
  flex-shrink: 0;
}

.content {
  flex: 1;
  overflow: auto;
  padding: 24px;
}

.btn {
  height: 40px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid var(--line-color);
  background: #fff;
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.18s ease;
}

.btn-sm {
  height: 38px;
  padding: 0 14px;
  font-size: 13px;
}

.btn-primary {
  background: linear-gradient(135deg, var(--brand) 0%, #3b82f6 100%);
  border-color: var(--brand);
  color: #fff;
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.18);
}

.btn-primary:hover {
  background: linear-gradient(135deg, var(--brand-hover) 0%, #2563eb 100%);
}

.btn-secondary:hover {
  background: #f8fafc;
}

.login-btn {
  width: 100%;
  height: 50px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
}

.login-version {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-sub);
}

.login-version-label {
  font-size: 12px;
  letter-spacing: 0.3px;
}

.login-version-value {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid var(--line-soft);
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1100px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-hero {
    min-height: auto;
  }
}

@media (max-width: 768px) {

  html,
  body {
    overflow: auto;
  }

  .login-page {
    align-items: flex-start;
    justify-content: flex-start;
    padding: 16px;
  }

  .login-shell {
    max-width: none;
    gap: 16px;
  }

  .login-hero,
  .login-card {
    border-radius: 22px;
  }

  .login-hero {
    min-height: auto;
    padding: 24px 20px;
  }

  .login-title {
    font-size: 28px;
    line-height: 1.28;
  }

  .login-subtitle {
    font-size: 14px;
    line-height: 1.8;
  }

  .login-points {
    gap: 8px;
    margin-top: 18px;
  }

  .login-points span {
    padding: 8px 12px;
    font-size: 12px;
  }

  .login-hero-footer {
    margin-top: 20px;
    padding-top: 14px;
  }

  .login-card {
    padding: 22px 20px;
  }

  .login-card-header h2 {
    font-size: 24px;
  }

  .login-btn {
    height: 48px;
  }
}

@media (max-width: 900px) {
  .layout {
    position: relative;
  }

  .mobile-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 58px;
    padding: 0 12px;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line-soft);
    z-index: 120;
  }

  .mobile-topbar-title {
    font-size: 16px;
    font-weight: 800;
    color: var(--text-main);
    flex: 1;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mobile-menu-btn,
  .mobile-logout-btn {
    flex-shrink: 0;
  }

  .mobile-menu-btn {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    border: 1px solid var(--line-color);
    background: #fff;
    color: var(--text-main);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    cursor: pointer;
  }

  .mobile-sidebar-mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.32);
    z-index: 109;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 256px;
    max-width: 82vw;
    z-index: 110;
    transform: translateX(-100%);
    transition: transform 0.22s ease;
    padding-top: 12px;
  }

  .sidebar.mobile-open {
    transform: translateX(0);
  }

  .sidebar.collapsed {
    width: 256px;
    padding-left: 12px;
    padding-right: 12px;
  }

  .main {
    width: 100%;
  }

  .header {
    display: none;
  }

  .content {
    padding: 74px 12px 16px;
  }
}
</style>
