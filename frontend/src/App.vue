<template>
  <div v-if="isLoginPage" class="login-page">
    <div class="login-background-grid"></div>
    <div class="login-shell">
      <section class="login-hero">
        <div class="login-brand-lockup">
          <div class="login-logo-mark">督</div>
          <div>
            <div class="login-badge">
              <span class="login-badge-dot"></span>
              业务督导中心
            </div>
            <div class="login-release-note">巡检系统已上线</div>
          </div>
        </div>

        <h1 class="login-title">
          <span>业务督导中心</span>
          <span>数智管理平台</span>
        </h1>

        <p class="login-subtitle">
          面向巡检登记、整改复核、规范库和记录追踪的统一工作入口。
        </p>

        <div class="login-module-strip">
          <span class="active">巡检系统 已上线</span>
          <span>考核系统 规划中</span>
          <span>培训系统 规划中</span>
        </div>

        <div class="login-release-row">
          <span>当前版本 v{{ appVersion }}</span>
          <button class="login-version-history-btn" type="button" @click="loginVersionModalOpen = true">
            查看版本历史
          </button>
        </div>
      </section>

      <form class="login-card" @submit.prevent="handleLogin">
        <div class="login-card-header">
          <div class="login-card-kicker">工作台登录</div>
          <h2>账号登录</h2>
          <p>使用业务督导中心账号继续处理今日工作。</p>
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

    <div v-if="loginVersionModalOpen" class="login-version-modal" @click.self="loginVersionModalOpen = false">
      <div class="login-version-dialog">
        <div class="login-version-dialog-header">
          <div>
            <span>版本记录</span>
            <h2>业务督导中心更新历史</h2>
          </div>
          <button type="button" class="login-version-close" @click="loginVersionModalOpen = false">×</button>
        </div>

        <div class="login-version-history">
          <div v-for="entry in versionHistory" :key="entry.version" class="login-version-history-item">
            <div class="login-version-history-main">
              <strong>{{ entry.version }}</strong>
              <span>{{ entry.date }}</span>
            </div>
            <div class="login-version-history-content">
              <h3>{{ entry.title }}</h3>
              <p>{{ entry.summary }}</p>
              <ul>
                <li v-for="item in entry.items" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
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
          <span class="nav-item-icon">图</span>
          <span v-if="!sidebarCollapsed">站点地图</span>
        </button>
      </div>

      <div class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">巡检系统</div>

        <button v-if="canSubmitInspections" class="nav-item"
          :class="{ active: isActive('/inspection/register'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/register')" :title="sidebarCollapsed ? '巡检登记' : ''">
          <span class="nav-item-icon">登</span>
          <span v-if="!sidebarCollapsed">巡检登记</span>
        </button>

        <button v-if="canViewInspectionStandards" class="nav-item"
          :class="{ active: isActive('/inspection/standards'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/standards')" :title="sidebarCollapsed ? '巡检规范库' : ''">
          <span class="nav-item-icon">规</span>
          <span v-if="!sidebarCollapsed">巡检规范库</span>
        </button>

        <button v-if="canViewChecklistOriginals" class="nav-item"
          :class="{ active: isActive('/inspection/checklist-originals'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/checklist-originals')" :title="sidebarCollapsed ? '检查表原件库' : ''">
          <span class="nav-item-icon">件</span>
          <span v-if="!sidebarCollapsed">检查表原件库</span>
        </button>

        <button class="nav-item" :class="{ active: isActive('/inspection/my-issues'), collapsed: sidebarCollapsed }"
          type="button" @click="go('/inspection/my-issues')"
          :title="sidebarCollapsed ? (currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题') : ''">
          <span class="nav-item-icon">待</span>
          <span v-if="!sidebarCollapsed">{{ currentRole === 'station_manager' ? '我的待整改问题' : '我的待复核问题' }}</span>
        </button>

        <button v-if="canViewIssues" class="nav-item"
          :class="{ active: isActive('/inspection/issues'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/issues')" :title="sidebarCollapsed ? '巡检问题列表' : ''">
          <span class="nav-item-icon">问</span>
          <span v-if="!sidebarCollapsed">巡检问题列表</span>
        </button>

        <button v-if="canViewRecords" class="nav-item"
          :class="{ active: isActive('/inspection/records'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/records')" :title="sidebarCollapsed ? '巡检记录' : ''">
          <span class="nav-item-icon">录</span>
          <span v-if="!sidebarCollapsed">巡检记录</span>
        </button>

        <button v-if="canViewInspectionPlans" class="nav-item"
          :class="{ active: isActive('/inspection/plan'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/plan')" :title="sidebarCollapsed ? '巡检计划' : ''">
          <span class="nav-item-icon">计</span>
          <span v-if="!sidebarCollapsed">巡检计划</span>
        </button>

        <button v-if="canViewCertificates" class="nav-item"
          :class="{ active: isActive('/inspection/certificates'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/inspection/certificates')" :title="sidebarCollapsed ? '证照管理' : ''">
          <span class="nav-item-icon">证</span>
          <span v-if="!sidebarCollapsed">证照管理</span>
        </button>
      </div>

      <div v-if="canViewAssessment" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">考核系统</div>
        <button class="nav-item" :class="{ active: isActive('/assessment'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/assessment')" :title="sidebarCollapsed ? '考核系统' : ''">
          <span class="nav-item-icon">考</span>
          <span v-if="!sidebarCollapsed">考核系统</span>
        </button>
      </div>

      <div v-if="canViewTrainingSection" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">培训系统</div>
        <button v-if="canViewTrainingInternal" class="nav-item"
          :class="{ active: isActive('/training'), collapsed: sidebarCollapsed }" type="button" @click="go('/training')"
          :title="sidebarCollapsed ? '培训系统' : ''">
          <span class="nav-item-icon">培</span>
          <span v-if="!sidebarCollapsed">培训系统</span>
        </button>
        <button v-if="canViewTrainingMaterials" class="nav-item"
          :class="{ active: isActive('/training/materials'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/training/materials')" :title="sidebarCollapsed ? '培训材料库' : ''">
          <span class="nav-item-icon">材</span>
          <span v-if="!sidebarCollapsed">培训材料库</span>
        </button>
      </div>

      <div v-if="currentRole !== 'station_manager'" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">车辆系统</div>
        <button class="nav-item" :class="{ active: isActive('/vehicle'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/vehicle')" :title="sidebarCollapsed ? '车辆管理系统' : ''">
          <span class="nav-item-icon">车</span>
          <span v-if="!sidebarCollapsed">车辆管理系统</span>
        </button>
      </div>

      <div class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">公共功能</div>
        <button class="nav-item" :class="{ active: isActive('/feedback'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/feedback')" :title="sidebarCollapsed ? '系统反馈' : ''">
          <span class="nav-item-icon">馈</span>
          <span v-if="!sidebarCollapsed">系统反馈</span>
        </button>
      </div>

      <div v-if="canViewManagementSection" class="menu-section">
        <div v-if="!sidebarCollapsed" class="menu-section-title">管理系统</div>
        <button v-if="canManageUsers" class="nav-item"
          :class="{ active: isActive('/management/users'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/users')" :title="sidebarCollapsed ? '用户数据管理' : ''">
          <span class="nav-item-icon">用</span>
          <span v-if="!sidebarCollapsed">用户数据管理</span>
        </button>
        <button v-if="canManageStations" class="nav-item"
          :class="{ active: isActive('/management/stations'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/stations')" :title="sidebarCollapsed ? '站点数据管理' : ''">
          <span class="nav-item-icon">站</span>
          <span v-if="!sidebarCollapsed">站点数据管理</span>
        </button>
        <button v-if="canManageChecklists" class="nav-item"
          :class="{ active: isActive('/management/checklists'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/checklists')" :title="sidebarCollapsed ? '巡检表数据管理' : ''">
          <span class="nav-item-icon">表</span>
          <span v-if="!sidebarCollapsed">巡检表数据管理</span>
        </button>
        <button v-if="canManageBackups" class="nav-item"
          :class="{ active: isActive('/management/backups'), collapsed: sidebarCollapsed }" type="button"
          @click="go('/management/backups')" :title="sidebarCollapsed ? '数据备份管理' : ''">
          <span class="nav-item-icon">备</span>
          <span v-if="!sidebarCollapsed">数据备份管理</span>
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

    <div v-if="authState.mustChangePassword" class="force-password-overlay" role="dialog" aria-modal="true">
      <form class="force-password-card" @submit.prevent="handlePasswordChange">
        <div class="force-password-eyebrow">首次登录安全校验</div>
        <h2>请先设置新密码</h2>
        <p class="force-password-subtitle">
          当前账号仍在使用初始密码。为了保护业务数据安全，完成密码更新后再进入系统。
        </p>

        <div class="force-password-user">
          <span>当前账号</span>
          <strong>{{ authState.realName || authState.username }}</strong>
        </div>

        <div class="force-password-fields">
          <label>
            <span>当前密码</span>
            <input v-model="passwordChangeForm.currentPassword" type="password" autocomplete="current-password"
              placeholder="请输入当前密码" />
          </label>
          <label>
            <span>新密码</span>
            <input v-model="passwordChangeForm.newPassword" type="password" autocomplete="new-password"
              placeholder="8-32 位，包含字母和数字" />
          </label>
          <label>
            <span>确认新密码</span>
            <input v-model="passwordChangeForm.confirmPassword" type="password" autocomplete="new-password"
              placeholder="请再次输入新密码" />
          </label>
        </div>

        <div class="force-password-rules">
          <span :class="{ passed: passwordRuleStatus.length }">8-32 位</span>
          <span :class="{ passed: passwordRuleStatus.letterAndNumber }">包含字母和数字</span>
          <span :class="{ passed: passwordRuleStatus.noWhitespace }">不含空格</span>
          <span :class="{ passed: passwordRuleStatus.notDefaultOrUsername }">不使用初始密码或用户名</span>
          <span :class="{ passed: passwordRuleStatus.confirmed }">两次输入一致</span>
        </div>

        <div v-if="passwordChangeError" class="force-password-message error">{{ passwordChangeError }}</div>
        <div v-if="passwordChangeSuccess" class="force-password-message success">{{ passwordChangeSuccess }}</div>

        <div class="force-password-actions">
          <button class="btn btn-secondary" type="button" :disabled="passwordChangeSaving" @click="handleLogout">
            退出登录
          </button>
          <button class="btn btn-primary" type="submit" :disabled="passwordChangeSaving">
            {{ passwordChangeSaving ? '正在保存...' : '保存新密码' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useRoute, useRouter } from 'vue-router'
import appPackage from '../package.json'
import { clearAuthSession, storeAuthSession, syncAxiosAuthHeader } from './utils/authSession'

const router = useRouter()
const route = useRoute()

const loginForm = reactive({
  username: '',
  password: ''
})

const passwordChangeForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const loginError = ref('')
const passwordChangeError = ref('')
const passwordChangeSuccess = ref('')
const passwordChangeSaving = ref(false)
const sidebarCollapsed = ref(false)
const mobileMenuOpen = ref(false)
const loginVersionModalOpen = ref(false)
const defaultInitialPassword = '123456'

const parseStoredPermissions = () => {
  try {
    return JSON.parse(localStorage.getItem('permissions') || '{}')
  } catch (error) {
    return {}
  }
}

const getStoredMustChangePassword = () => localStorage.getItem('must_change_password') === 'true'

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
  mustChangePassword: getStoredMustChangePassword(),
  permissions: parseStoredPermissions()
})

syncAxiosAuthHeader()

const isLoginPage = computed(() => route.path === '/login')
const formatAppVersion = (value) => {
  const [major = '1', minor = '0'] = String(value || '1.0').split('.')
  const normalizedMajor = Number.parseInt(major, 10)
  const normalizedMinor = Number.parseInt(minor, 10)
  return `${Number.isFinite(normalizedMajor) ? normalizedMajor : 1}.${Number.isFinite(normalizedMinor) ? normalizedMinor : 0}`
}
const appVersion = formatAppVersion(appPackage.version || '1.0.0')
const versionHistory = [
  {
    version: 'v1.0',
    date: '2026-05-07',
    title: '巡检系统上线发布',
    summary: '首个正式版本聚焦巡检业务闭环，考核系统和培训系统将随后续版本逐步完善。',
    items: [
      '上线巡检登记、问题列表、我的待复核/待整改问题与巡检记录。',
      '上线巡检规范库与检查表原件库，支持规范查询和原始文件查看。',
      '上线巡检计划、站点地图移动端事件流等巡检辅助能力。'
    ]
  }
]
const currentRole = computed(() => authState.role)
const currentUsername = computed(() => authState.realName || authState.username || '未命名用户')
const localPermissions = computed(() => authState.permissions || {})
const passwordRuleStatus = computed(() => {
  const password = passwordChangeForm.newPassword
  const confirmPassword = passwordChangeForm.confirmPassword
  const username = authState.username || ''

  return {
    length: password.length >= 8 && password.length <= 32,
    letterAndNumber: /[A-Za-z]/.test(password) && /\d/.test(password),
    noWhitespace: password.length > 0 && !/\s/.test(password),
    notDefaultOrUsername: Boolean(
      password &&
      password !== defaultInitialPassword &&
      (!username || password.toLowerCase() !== username.toLowerCase())
    ),
    confirmed: Boolean(confirmPassword && password === confirmPassword)
  }
})
const isRoot = computed(() => authState.role === 'root')
const isSupervisor = computed(() => authState.role === 'supervisor')
const isStationManager = computed(() => authState.role === 'station_manager')
const hasPermissionKey = (key) => authState.role === 'root' || Boolean(localPermissions.value[key])
const canViewStationMap = computed(() => hasPermissionKey('view_station_map'))
const canSubmitInspections = computed(() => hasPermissionKey('submit_inspections'))
const canViewInspectionStandards = computed(() => hasPermissionKey('view_inspection_standards'))
const canViewChecklistOriginals = computed(() => hasPermissionKey('view_checklist_originals'))
const canViewIssues = computed(() => (
  isRoot.value ||
  Boolean(localPermissions.value.view_all_inspection_issues) ||
  Boolean(localPermissions.value.view_own_inspection_issues) ||
  Boolean(localPermissions.value.submit_inspections)
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
const canManageUsers = computed(() => isRoot.value)
const canManageStations = computed(() => hasPermissionKey('manage_stations'))
const canManageChecklists = computed(() => hasPermissionKey('manage_checklists'))
const canManageBackups = computed(() => isRoot.value)
const canViewManagementSection = computed(() => (
  canManageUsers.value ||
  canManageStations.value ||
  canManageChecklists.value ||
  canManageBackups.value
))
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
  authState.mustChangePassword = getStoredMustChangePassword()
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
  if (permissions.manage_stations) return '/management/stations'
  if (permissions.manage_checklists) return '/management/checklists'
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
  const nextOpen = !mobileMenuOpen.value
  mobileMenuOpen.value = nextOpen
  if (nextOpen) sidebarCollapsed.value = false
}

const closeMobileMenu = () => {
  mobileMenuOpen.value = false
}

const resetPasswordChangeForm = () => {
  passwordChangeForm.currentPassword = ''
  passwordChangeForm.newPassword = ''
  passwordChangeForm.confirmPassword = ''
  passwordChangeError.value = ''
  passwordChangeSuccess.value = ''
  passwordChangeSaving.value = false
}

const getPasswordChangeClientError = () => {
  if (!passwordChangeForm.currentPassword) return '请输入当前密码。'
  if (!passwordChangeForm.newPassword) return '请填写新密码。'
  if (!passwordRuleStatus.value.length) return '新密码长度需为 8-32 位。'
  if (!passwordRuleStatus.value.noWhitespace) return '新密码不能包含空格。'
  if (!passwordRuleStatus.value.letterAndNumber) return '新密码需同时包含字母和数字。'
  if (!passwordRuleStatus.value.notDefaultOrUsername) return '新密码不能使用初始密码或用户名。'
  if (!passwordRuleStatus.value.confirmed) return '两次输入的新密码不一致。'
  if (passwordChangeForm.currentPassword === passwordChangeForm.newPassword) return '新密码不能与当前密码相同。'
  return ''
}

const handlePasswordChange = async () => {
  passwordChangeError.value = ''
  passwordChangeSuccess.value = ''

  const clientError = getPasswordChangeClientError()
  if (clientError) {
    passwordChangeError.value = clientError
    return
  }

  try {
    passwordChangeSaving.value = true
    const response = await axios.post('/api/users/change-password', {
      user_id: authState.userId,
      current_password: passwordChangeForm.currentPassword,
      new_password: passwordChangeForm.newPassword,
      confirm_password: passwordChangeForm.confirmPassword
    })

    if (response.data?.token && response.data?.user) {
      storeAuthSession(response.data.user, response.data.token)
    } else {
      localStorage.setItem('must_change_password', 'false')
      syncAxiosAuthHeader()
    }

    passwordChangeSuccess.value = '新密码已保存，正在进入系统。'
    window.setTimeout(() => {
      syncAuthState()
      resetPasswordChangeForm()
    }, 650)
  } catch (error) {
    passwordChangeError.value = error?.response?.data?.error || '密码修改失败，请稍后重试。'
    passwordChangeSaving.value = false
  }
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
    const token = response.data.token
    if (!token) {
      loginError.value = '登录响应缺少服务端令牌，请联系管理员。'
      return
    }

    storeAuthSession(user, token)

    resetPasswordChangeForm()
    syncAuthState()
    loginForm.password = ''
    router.push(resolveHomePath(user))
  } catch (error) {
    const message = error?.response?.data?.error || '登录失败，请稍后重试。'
    loginError.value = message
  }
}

const handleLogout = () => {
  clearAuthSession()
  resetPasswordChangeForm()
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
  --sidebar-bg:
    radial-gradient(circle at 20% 0%, rgba(59, 130, 246, 0.24), transparent 30%),
    linear-gradient(180deg, #0f1b32 0%, #0b1220 52%, #08111f 100%);
  --sidebar-text: rgba(241, 245, 249, 0.9);
  --sidebar-muted: rgba(203, 213, 225, 0.58);
  --sidebar-panel: rgba(255, 255, 255, 0.055);
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
  height: 100dvh;
  box-sizing: border-box;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(10px, 2.2vh, 22px);
  overflow: hidden;
  background:
    radial-gradient(circle at 16% 18%, rgba(14, 165, 233, 0.12), transparent 30%),
    radial-gradient(circle at 88% 78%, rgba(37, 99, 235, 0.10), transparent 30%),
    linear-gradient(145deg, #f7fbff 0%, #edf4f8 52%, #e7eef5 100%);
}

.login-page::before {
  content: '';
  position: absolute;
  left: 50%;
  bottom: clamp(4px, 1.4vh, 14px);
  width: min(880px, 82vw);
  height: 92px;
  transform: translateX(-50%);
  border-radius: 999px;
  background:
    radial-gradient(ellipse at center, rgba(37, 99, 235, 0.18) 0%, rgba(14, 165, 233, 0.08) 42%, transparent 72%);
  filter: blur(8px);
  pointer-events: none;
  z-index: 0;
}

.login-page::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: clamp(18px, 3vh, 34px);
  width: min(720px, 70vw);
  height: 1px;
  transform: translateX(-50%);
  background: linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.22), transparent);
  pointer-events: none;
  z-index: 0;
}

.login-background-grid {
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.58;
  background-image:
    linear-gradient(rgba(15, 23, 42, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.035) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.82), transparent 82%);
  -webkit-mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.82), transparent 82%);
}

.login-shell {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1220px;
  height: min(660px, calc(100dvh - 28px));
  display: grid;
  grid-template-columns: minmax(0, 1fr) 390px;
  gap: 0;
  align-items: stretch;
  overflow: hidden;
  border: 1px solid rgba(203, 213, 225, 0.78);
  border-radius: 34px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow:
    0 28px 80px rgba(15, 23, 42, 0.14),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(20px) saturate(1.08);
  -webkit-backdrop-filter: blur(20px) saturate(1.08);
}

.login-hero,
.login-card {
  border: none;
  border-radius: 0;
  box-shadow: none;
}

.login-hero {
  position: relative;
  overflow: hidden;
  padding: 42px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  min-height: 0;
  color: #e2e8f0;
  background:
    radial-gradient(circle at 18% 18%, rgba(125, 211, 252, 0.24), transparent 35%),
    radial-gradient(circle at 92% 8%, rgba(96, 165, 250, 0.22), transparent 34%),
    linear-gradient(135deg, #0f2437 0%, #123b63 54%, #174d7c 100%);
}

.login-hero::before,
.login-hero::after {
  content: '';
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
}

.login-hero::before {
  right: -84px;
  top: -92px;
  width: 230px;
  height: 230px;
  background: rgba(56, 189, 248, 0.18);
  border: 1px solid rgba(186, 230, 253, 0.22);
}

.login-hero::after {
  left: 52px;
  bottom: -120px;
  width: 260px;
  height: 260px;
  background: rgba(59, 130, 246, 0.18);
  filter: blur(10px);
}

.login-brand-lockup {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.login-logo-mark {
  width: 52px;
  height: 52px;
  border-radius: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
  font-weight: 900;
  background:
    radial-gradient(circle at 30% 20%, rgba(255, 255, 255, 0.42), transparent 30%),
    linear-gradient(135deg, #38bdf8 0%, #2563eb 60%, #1d4ed8 100%);
  box-shadow: 0 18px 34px rgba(37, 99, 235, 0.24);
}

.login-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  width: fit-content;
  padding: 0;
  border-radius: 999px;
  background: transparent;
  border: none;
  color: #dbeafe;
  font-size: 13px;
  font-weight: 900;
  margin-bottom: 0;
  box-shadow: none;
}

.login-badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 0 5px rgba(56, 189, 248, 0.13), 0 0 18px rgba(56, 189, 248, 0.7);
}

.login-release-note {
  margin-top: 4px;
  color: #9cc9f5;
  font-size: 12px;
  font-weight: 800;
}

.login-title {
  position: relative;
  z-index: 1;
  display: inline-flex;
  flex-direction: row;
  align-items: baseline;
  width: fit-content;
  margin: 0;
  max-width: none;
  font-size: clamp(40px, 4vw, 56px);
  font-weight: 900;
  line-height: 1.02;
  letter-spacing: -1.8px;
  color: #f8fafc;
}

.login-title span {
  display: block;
  white-space: nowrap;
}

.login-subtitle {
  position: relative;
  z-index: 1;
  margin: 0;
  color: #cbd5e1;
  font-size: 14px;
  line-height: 1.72;
  max-width: 460px;
}

.login-module-strip {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.login-module-strip span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(226, 232, 240, 0.14);
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 900;
}

.login-module-strip span.active {
  background: rgba(37, 99, 235, 0.22);
  border-color: rgba(147, 197, 253, 0.3);
  color: #dbeafe;
}

.login-release-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  width: 100%;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid rgba(191, 219, 254, 0.24);
  color: #93c5fd;
  font-size: 13px;
  font-weight: 900;
}

.login-version-history-btn {
  width: fit-content;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(147, 197, 253, 0.24);
  background: rgba(255, 255, 255, 0.08);
  color: #dbeafe;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
  transition: all 0.18s ease;
}

.login-version-history-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  border-color: rgba(147, 197, 253, 0.38);
}

.login-card {
  padding: 42px 38px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid rgba(226, 232, 240, 0.9);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
    #fff;
}

.login-card-header {
  margin-bottom: 24px;
}

.login-card-kicker {
  width: fit-content;
  margin-bottom: 12px;
  padding: 7px 12px;
  border-radius: 999px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid rgba(37, 99, 235, 0.12);
  font-size: 12px;
  font-weight: 900;
}

.login-card-header h2 {
  margin: 0 0 8px;
  font-size: 32px;
  letter-spacing: -0.8px;
  color: #0f172a;
}

.login-card-header p {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
}

.login-version-modal {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  background: rgba(15, 23, 42, 0.46);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.login-version-dialog {
  width: min(620px, 100%);
  max-height: min(720px, calc(100vh - 44px));
  overflow: auto;
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.11), transparent 34%),
    #fff;
  border: 1px solid rgba(203, 213, 225, 0.9);
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.26);
}

.login-version-dialog-header {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 24px 18px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.82);
}

.login-version-dialog-header span {
  display: inline-flex;
  margin-bottom: 8px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
}

.login-version-dialog-header h2 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  letter-spacing: -0.6px;
}

.login-version-close {
  width: 38px;
  height: 38px;
  border-radius: 14px;
  border: 1px solid #dbe4ee;
  background: #f8fafc;
  color: #334155;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.login-version-history {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 24px 24px;
}

.login-version-history-item {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 18px;
  padding: 18px;
  border-radius: 22px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.login-version-history-main strong {
  display: block;
  margin-bottom: 6px;
  color: #1d4ed8;
  font-size: 22px;
  line-height: 1;
  font-weight: 900;
}

.login-version-history-main span {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.login-version-history-content h3 {
  margin: 0 0 8px;
  color: #0f172a;
  font-size: 18px;
}

.login-version-history-content p {
  margin: 0 0 12px;
  color: #475569;
  font-size: 14px;
  line-height: 1.75;
}

.login-version-history-content ul {
  margin: 0;
  padding-left: 18px;
  color: #334155;
  font-size: 14px;
  line-height: 1.85;
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

.force-password-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at 30% 18%, rgba(14, 165, 233, 0.18), transparent 32%),
    rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.force-password-card {
  width: min(520px, 100%);
  max-height: calc(100dvh - 48px);
  overflow: auto;
  border: 1px solid rgba(203, 213, 225, 0.88);
  border-radius: 30px;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.1), transparent 34%),
    #fff;
  box-shadow: 0 30px 90px rgba(15, 23, 42, 0.36);
}

.force-password-eyebrow {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  margin-bottom: 12px;
  padding: 7px 12px;
  border-radius: 999px;
  color: #1d4ed8;
  background: #eff6ff;
  border: 1px solid rgba(37, 99, 235, 0.13);
  font-size: 12px;
  font-weight: 900;
}

.force-password-card h2 {
  margin: 0;
  color: #0f172a;
  font-size: 28px;
  letter-spacing: -0.7px;
}

.force-password-subtitle {
  margin: 10px 0 18px;
  color: #475569;
  font-size: 14px;
  line-height: 1.75;
}

.force-password-user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
  padding: 12px 14px;
  border-radius: 18px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.force-password-user span {
  color: #64748b;
  font-size: 13px;
  font-weight: 800;
}

.force-password-user strong {
  color: #0f172a;
  font-size: 15px;
}

.force-password-fields {
  display: grid;
  gap: 14px;
}

.force-password-fields label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  color: #334155;
  font-size: 14px;
  font-weight: 800;
}

.force-password-fields input {
  width: 100%;
  height: 48px;
  border: 1px solid var(--line-color);
  border-radius: 15px;
  padding: 0 14px;
  background: #fff;
  color: var(--text-main);
  transition: all 0.18s ease;
}

.force-password-fields input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.42);
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

.force-password-rules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.force-password-rules span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 12px;
  font-weight: 900;
}

.force-password-rules span.passed {
  background: #ecfdf5;
  border-color: #bbf7d0;
  color: #047857;
}

.force-password-message {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.6;
}

.force-password-message.error {
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.force-password-message.success {
  color: #047857;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
}

.force-password-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
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
  padding: 16px 12px 18px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.04);
  transition: width 0.22s ease, padding 0.22s ease;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
}

.sidebar::-webkit-scrollbar {
  width: 6px;
}

.sidebar::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.32);
  border-radius: 999px;
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px;
  margin-bottom: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.11), rgba(255, 255, 255, 0.045)),
    rgba(15, 23, 42, 0.18);
  box-shadow: 0 18px 38px rgba(0, 0, 0, 0.16);
}

.logo-mark {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  background:
    radial-gradient(circle at 28% 18%, rgba(255, 255, 255, 0.38), transparent 34%),
    linear-gradient(135deg, #38bdf8 0%, #2563eb 58%, #1e40af 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 900;
  box-shadow: 0 14px 24px rgba(37, 99, 235, 0.28);
}

.logo-title {
  max-width: 150px;
  font-size: 17px;
  font-weight: 900;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logo-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: var(--sidebar-muted);
}

.menu-section {
  position: relative;
  margin-top: 16px;
  padding-top: 16px;
}

.menu-section::before {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  top: 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.22), transparent);
}

.sidebar-top+.menu-section {
  margin-top: 6px;
}

.sidebar-top+.menu-section::before {
  display: none;
}

.menu-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  margin-bottom: 9px;
  font-size: 11px;
  letter-spacing: 1.2px;
  color: var(--sidebar-muted);
  font-weight: 900;
}

.menu-section-title::after {
  content: "";
  height: 1px;
  flex: 1;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.18), transparent);
}

.nav-item {
  position: relative;
  width: 100%;
  border: none;
  background: transparent;
  color: var(--sidebar-text);
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 42px;
  padding: 8px 11px;
  border-radius: 13px;
  cursor: pointer;
  margin-bottom: 5px;
  text-align: left;
  font-size: 14px;
  font-weight: 760;
  letter-spacing: 0.1px;
  overflow: hidden;
  transition: transform 0.18s ease, background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}

.nav-item:hover {
  transform: translateX(2px);
  background: rgba(255, 255, 255, 0.075);
  color: #fff;
}

.nav-item.active {
  background:
    linear-gradient(90deg, rgba(59, 130, 246, 0.32) 0%, rgba(14, 165, 233, 0.14) 100%),
    var(--sidebar-panel);
  color: #fff;
  box-shadow:
    inset 0 0 0 1px rgba(125, 211, 252, 0.2),
    0 10px 22px rgba(2, 6, 23, 0.18);
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 14px rgba(56, 189, 248, 0.72);
}

.nav-item-icon {
  width: 26px;
  height: 26px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.13);
  border: 1px solid rgba(203, 213, 225, 0.12);
  color: rgba(226, 232, 240, 0.82);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 900;
  transition: all 0.18s ease;
}

.nav-item:hover .nav-item-icon {
  background: rgba(255, 255, 255, 0.13);
  border-color: rgba(203, 213, 225, 0.2);
  color: #fff;
}

.nav-item.active .nav-item-icon {
  background: linear-gradient(135deg, #38bdf8 0%, #2563eb 100%);
  border-color: rgba(191, 219, 254, 0.36);
  color: #fff;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.28);
}

.sidebar.collapsed {
  width: 82px;
  padding: 14px 10px 18px;
}

.sidebar.collapsed .sidebar-top {
  justify-content: center;
  padding: 8px;
  border-radius: 18px;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.nav-item.collapsed {
  justify-content: center;
  min-height: 44px;
  padding-left: 0;
  padding-right: 0;
  border-radius: 16px;
}

.nav-item.collapsed:hover {
  transform: translateY(-1px);
}

.nav-item.collapsed.active::before {
  left: 4px;
}

.nav-item.collapsed .nav-item-icon {
  width: 32px;
  height: 32px;
  border-radius: 12px;
}

.sidebar-toggle {
  width: 38px;
  height: 38px;
  border-radius: 13px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.075);
  color: #e2e8f0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.18s ease;
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  transform: translateY(-1px);
}

.header-left-block {
  display: flex;
  align-items: center;
  min-width: 0;
}

.sidebar-collapsed-layout .sidebar {
  width: 82px;
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

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.62;
  transform: none;
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
    max-width: 980px;
    grid-template-columns: minmax(0, 1fr) 360px;
  }

  .login-hero {
    padding: 34px;
  }

  .login-title {
    font-size: clamp(34px, 3.8vw, 42px);
  }
}

@media (max-width: 768px) {

  html,
  body {
    overflow: auto;
  }

  .login-page {
    align-items: center;
    justify-content: center;
    height: auto;
    min-height: 100dvh;
    padding: 8px 10px;
    overflow: auto;
  }

  .login-page::before {
    bottom: 0;
    width: 92vw;
    height: 76px;
    filter: blur(6px);
  }

  .login-page::after {
    bottom: 12px;
    width: 78vw;
  }

  .login-shell {
    display: flex;
    flex-direction: column;
    min-height: auto;
    height: auto;
    width: min(100%, 420px);
    max-width: none;
    gap: 0;
    border-radius: 28px;
  }

  .login-hero,
  .login-card {
    border-radius: 0;
  }

  .login-hero {
    min-height: auto;
    padding: 18px 18px 14px;
    gap: 10px;
    align-items: center;
    text-align: center;
  }

  .login-brand-lockup {
    flex-direction: column;
    gap: 8px;
  }

  .login-logo-mark {
    width: 44px;
    height: 44px;
    border-radius: 16px;
    font-size: 21px;
  }

  .login-badge,
  .login-release-note {
    width: 100%;
    justify-content: center;
    text-align: center;
  }

  .login-title {
    flex-direction: column;
    align-items: center;
    font-size: 28px;
    line-height: 1.08;
    letter-spacing: -0.5px;
  }

  .login-subtitle {
    font-size: 13px;
    line-height: 1.55;
  }

  .login-module-strip {
    display: none;
  }

  .login-release-row {
    justify-content: center;
    gap: 8px;
    font-size: 12px;
    margin-top: 2px;
    padding-top: 10px;
  }

  .login-version-history-btn {
    height: 30px;
    padding: 0 10px;
  }

  .login-card {
    flex: none;
    justify-content: flex-start;
    min-height: auto;
    padding: 16px 18px 20px;
    border-left: none;
    border-top: 1px solid rgba(226, 232, 240, 0.9);
  }

  .login-card-header {
    margin-bottom: 16px;
  }

  .login-card-kicker {
    margin-bottom: 8px;
  }

  .login-card-header h2 {
    font-size: 24px;
  }

  .form-item {
    margin-bottom: 14px;
  }

  .login-btn {
    height: 48px;
  }

  .login-version-modal {
    align-items: flex-end;
    padding: 12px;
  }

  .login-version-dialog {
    max-height: calc(100vh - 24px);
    border-radius: 24px;
  }

  .login-version-dialog-header {
    padding: 20px 18px 16px;
  }

  .login-version-dialog-header h2 {
    font-size: 21px;
  }

  .login-version-history {
    padding: 16px 18px 18px;
  }

  .login-version-history-item {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 16px;
  }

  .force-password-overlay {
    align-items: stretch;
    padding: 12px;
  }

  .force-password-card {
    align-self: center;
    max-height: calc(100dvh - 24px);
    border-radius: 24px;
    padding: 22px 18px;
  }

  .force-password-card h2 {
    font-size: 24px;
  }

  .force-password-user {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .force-password-actions {
    flex-direction: column-reverse;
  }

  .force-password-actions .btn {
    width: 100%;
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
    z-index: 130;
  }

  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    width: 256px;
    max-width: 82vw;
    z-index: 140;
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
