import { createRouter, createWebHistory } from 'vue-router'
import InspectionStandardsView from '../views/inspection/InspectionStandardsView.vue'
import StationMapView from '../views/inspection/StationMapView.vue'
import { clearAuthSession, isUsableAuthToken, verifyAuthSession } from '../utils/authSession'
import { fetchPageVisibility, isPageVisibleInSnapshot } from '../utils/pageVisibility'

const EmptyRouteView = { template: '<div></div>' }

const routes = [
  {
    path: '/',
    redirect: '/inspection/issues'
  },
  {
    path: '/login',
    component: EmptyRouteView,
    meta: { public: true }
  },
  {
    path: '/inspection/issues',
    component: () => import('../views/inspection/IssuesView.vue')
  },
  {
    path: '/inspection/register',
    component: () => import('../views/inspection/RegisterView.vue'),
  },
  {
    path: '/inspection/standards',
    component: InspectionStandardsView
  },
  {
    path: '/inspection/checklist-originals',
    component: () => import('../views/inspection/ChecklistOriginalsView.vue')
  },
  {
    path: '/inspection/station-map',
    component: StationMapView
  },
  {
    path: '/inspection/records',
    component: () => import('../views/inspection/RecordsView.vue')
  },
  {
    path: '/inspection/plan',
    component: () => import('../views/inspection/PlanView.vue')
  },
  {
    path: '/inspection/reports',
    component: () => import('../views/inspection/ReportGeneratorView.vue')
  },
  {
    path: '/inspection/my-issues',
    component: () => import('../views/inspection/MyIssuesView.vue')
  },
  {
    path: '/assessment',
    component: () => import('../views/Assessment.vue')
  },
  {
    path: '/assessment/attendance',
    component: () => import('../views/assessment/AttendanceView.vue')
  },
  {
    path: '/assessment/station-score',
    component: () => import('../views/assessment/StationScoreView.vue')
  },
  {
    path: '/assessment/peer-review',
    component: () => import('../views/assessment/PeerReviewView.vue')
  },
  {
    path: '/training',
    component: () => import('../views/Training.vue')
  },
  {
    path: '/training/materials',
    component: () => import('../views/TrainingMaterialsView.vue')
  },
  {
    path: '/vehicle',
    component: () => import('../views/VehicleManagement.vue')
  },
  {
    path: '/management/users',
    component: () => import('../views/management/UserDataManagementView.vue')
  },
  {
    path: '/management/stations',
    component: () => import('../views/management/StationDataManagementView.vue')
  },
  {
    path: '/management/checklists',
    component: () => import('../views/management/ChecklistDataManagementView.vue')
  },
  {
    path: '/management/internal-standards',
    component: () => import('../views/management/InternalStandardsManagementView.vue')
  },
  {
    path: '/management/inspection-completion',
    component: () => import('../views/management/InspectionCompletionManagementView.vue')
  },
  {
    path: '/management/auto-audit',
    component: () => import('../views/management/AutoAuditManagementView.vue')
  },
  {
    path: '/management/ai-usage',
    component: () => import('../views/management/AiUsageManagementView.vue')
  },
  {
    path: '/management/page-visibility',
    component: () => import('../views/management/PageVisibilityManagementView.vue')
  },
  {
    path: '/management/backups',
    component: () => import('../views/management/BackupManagementView.vue')
  },
  {
    path: '/inspection/certificates',
    component: () => import('../views/inspection/CertificatesView.vue')
  },
  {
    path: '/feedback',
    component: () => import('../views/Feedback.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const hasPermission = (role, permissions, key) => role === 'root' || Boolean(permissions[key])

const canAccessPath = (path, role, permissions) => {
  if (role === 'root') return true
  if (path === '/management/page-visibility') return false
  if (path === '/management/stations') return hasPermission(role, permissions, 'manage_stations')
  if (path === '/management/checklists') return hasPermission(role, permissions, 'manage_checklists')
  if (path === '/management/internal-standards') return hasPermission(role, permissions, 'manage_internal_standards')
  if (path === '/management/auto-audit') return hasPermission(role, permissions, 'manage_auto_audit_rules')
  if (path === '/management/ai-usage') return hasPermission(role, permissions, 'manage_ai_usage')
  if (path === '/management/inspection-completion') return role === 'root'
  if (path.startsWith('/management')) return false
  if (path === '/inspection/station-map') return hasPermission(role, permissions, 'view_station_map')
  if (path === '/inspection/register') return hasPermission(role, permissions, 'submit_inspections')
  if (path === '/inspection/standards') return hasPermission(role, permissions, 'view_inspection_standards')
  if (path === '/inspection/checklist-originals') return hasPermission(role, permissions, 'view_checklist_originals')
  if (path === '/inspection/issues') {
    return Boolean(
      permissions.view_all_inspection_issues ||
      permissions.limit_issue_station_region_scope ||
      permissions.view_own_inspection_issues ||
      permissions.submit_inspections
    )
  }
  if (path === '/inspection/records') {
    return Boolean(
      permissions.view_all_inspection_records ||
      permissions.limit_record_station_region_scope ||
      permissions.view_own_inspection_records
    )
  }
  if (path === '/inspection/plan') return hasPermission(role, permissions, 'view_inspection_plans')
  if (path === '/inspection/reports') return hasPermission(role, permissions, 'view_inspection_reports')
  if (path === '/inspection/certificates') {
    return Boolean(
      permissions.view_all_certificates ||
      permissions.view_own_certificates ||
      permissions.edit_own_certificates
    )
  }
  if (path === '/inspection/my-issues') return ['supervisor', 'station_manager'].includes(role)
  if (path === '/assessment') return hasPermission(role, permissions, 'view_assessment')
  if (path === '/assessment/attendance') return hasPermission(role, permissions, 'view_attendance')
  if (path === '/assessment/station-score') return hasPermission(role, permissions, 'view_station_scores')
  if (path === '/assessment/peer-review') return hasPermission(role, permissions, 'view_peer_reviews')
  if (path === '/training') return hasPermission(role, permissions, 'view_training')
  if (path === '/training/materials') return hasPermission(role, permissions, 'view_training_materials')
  if (path === '/vehicle') return role === 'supervisor'
  return true
}

const resolveFallbackPath = (role, permissions, isPathVisible = () => true) => {
  const candidates = []
  if (role === 'root') {
    candidates.push(
      '/inspection/station-map',
      '/inspection/issues',
      '/inspection/records',
      '/management/page-visibility'
    )
  }
  if (role === 'station_manager') candidates.push('/inspection/my-issues')
  if (permissions.view_station_map) candidates.push('/inspection/station-map')
  if (permissions.submit_inspections) candidates.push('/inspection/register')
  if (permissions.view_inspection_standards) candidates.push('/inspection/standards')
  if (permissions.view_checklist_originals) candidates.push('/inspection/checklist-originals')
  if (permissions.view_all_inspection_issues || permissions.limit_issue_station_region_scope || permissions.view_own_inspection_issues) {
    candidates.push('/inspection/issues')
  }
  if (permissions.view_all_inspection_records || permissions.limit_record_station_region_scope || permissions.view_own_inspection_records) {
    candidates.push('/inspection/records')
  }
  if (permissions.view_inspection_plans) candidates.push('/inspection/plan')
  if (permissions.view_inspection_reports) candidates.push('/inspection/reports')
  if (permissions.view_all_certificates || permissions.view_own_certificates || permissions.edit_own_certificates) {
    candidates.push('/inspection/certificates')
  }
  if (permissions.view_attendance) candidates.push('/assessment/attendance')
  if (permissions.view_station_scores) candidates.push('/assessment/station-score')
  if (permissions.view_peer_reviews) candidates.push('/assessment/peer-review')
  if (permissions.view_assessment) candidates.push('/assessment')
  if (permissions.view_training) candidates.push('/training')
  if (permissions.view_training_materials) candidates.push('/training/materials')
  if (permissions.manage_stations) candidates.push('/management/stations')
  if (permissions.manage_checklists) candidates.push('/management/checklists')
  if (permissions.manage_internal_standards) candidates.push('/management/internal-standards')
  if (permissions.manage_auto_audit_rules) candidates.push('/management/auto-audit')
  if (permissions.manage_ai_usage) candidates.push('/management/ai-usage')
  if (role === 'root') {
    candidates.push('/management/inspection-completion', '/management/backups', '/management/page-visibility')
  }
  if (role === 'supervisor') candidates.push('/inspection/my-issues')
  candidates.push('/feedback')

  return candidates.find((path) => canAccessPath(path, role, permissions) && isPathVisible(path)) || '/feedback'
}

const verifyStoredAuthToken = async () => {
  const token = localStorage.getItem('auth_token')
  if (!isUsableAuthToken(token)) {
    clearAuthSession(token ? '登录已过期，请重新登录。' : '')
    return false
  }

  const result = await verifyAuthSession()
  return Boolean(result.ok)
}

const parseStoredPermissions = () => {
  try {
    return JSON.parse(localStorage.getItem('permissions') || '{}')
  } catch {
    return {}
  }
}

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('auth_token')

  if (to.meta.public) {
    if (to.path === '/login' && token && (await verifyStoredAuthToken())) {
      const verifiedRole = localStorage.getItem('user_role')
      const verifiedPermissions = parseStoredPermissions()
      const visibilitySettings = await fetchPageVisibility()
      next(resolveFallbackPath(
        verifiedRole,
        verifiedPermissions,
        (path) => isPageVisibleInSnapshot(path, visibilitySettings)
      ))
      return
    }
    next()
    return
  }

  if (!token || !(await verifyStoredAuthToken())) {
    next('/login')
    return
  }

  const verifiedRole = localStorage.getItem('user_role')
  const verifiedPermissions = parseStoredPermissions()

  if (!canAccessPath(to.path, verifiedRole, verifiedPermissions)) {
    const visibilitySettings = await fetchPageVisibility()
    next(resolveFallbackPath(
      verifiedRole,
      verifiedPermissions,
      (path) => isPageVisibleInSnapshot(path, visibilitySettings)
    ))
    return
  }

  const visibilitySettings = await fetchPageVisibility()
  const isPathVisible = (path) => isPageVisibleInSnapshot(path, visibilitySettings)
  if (!isPathVisible(to.path)) {
    const fallbackPath = resolveFallbackPath(verifiedRole, verifiedPermissions, isPathVisible)
    if (fallbackPath === to.path) {
      next()
      return
    }
    next(fallbackPath)
    return
  }

  next()
})

export default router
