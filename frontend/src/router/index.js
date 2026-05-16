import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import InspectionStandardsView from '../views/inspection/InspectionStandardsView.vue'
import StationMapView from '../views/inspection/StationMapView.vue'
import { clearAuthSession, isUsableAuthToken, storeAuthSession } from '../utils/authSession'

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
    path: '/inspection/my-issues',
    component: () => import('../views/inspection/MyIssuesView.vue')
  },
  {
    path: '/assessment',
    component: () => import('../views/Assessment.vue')
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
  if (path === '/management/stations') return hasPermission(role, permissions, 'manage_stations')
  if (path === '/management/checklists') return hasPermission(role, permissions, 'manage_checklists')
  if (path === '/management/internal-standards') return hasPermission(role, permissions, 'manage_internal_standards')
  if (path.startsWith('/management')) return false
  if (path === '/inspection/station-map') return hasPermission(role, permissions, 'view_station_map')
  if (path === '/inspection/register') return hasPermission(role, permissions, 'submit_inspections')
  if (path === '/inspection/standards') return hasPermission(role, permissions, 'view_inspection_standards')
  if (path === '/inspection/checklist-originals') return hasPermission(role, permissions, 'view_checklist_originals')
  if (path === '/inspection/issues') {
    return Boolean(
      permissions.view_all_inspection_issues ||
      permissions.view_own_inspection_issues ||
      permissions.submit_inspections
    )
  }
  if (path === '/inspection/records') {
    return Boolean(permissions.view_all_inspection_records || permissions.view_own_inspection_records)
  }
  if (path === '/inspection/plan') return hasPermission(role, permissions, 'view_inspection_plans')
  if (path === '/inspection/certificates') {
    return Boolean(
      permissions.view_all_certificates ||
      permissions.view_own_certificates ||
      permissions.edit_own_certificates
    )
  }
  if (path === '/inspection/my-issues') return ['supervisor', 'station_manager'].includes(role)
  if (path === '/assessment') return hasPermission(role, permissions, 'view_assessment')
  if (path === '/training') return hasPermission(role, permissions, 'view_training')
  if (path === '/training/materials') return hasPermission(role, permissions, 'view_training_materials')
  if (path === '/vehicle') return role === 'supervisor'
  return true
}

const resolveFallbackPath = (role, permissions) => {
  if (role === 'root') return '/inspection/station-map'
  if (role === 'station_manager') return '/inspection/my-issues'
  if (permissions.view_station_map) return '/inspection/station-map'
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
  if (permissions.manage_internal_standards) return '/management/internal-standards'
  if (role === 'supervisor') return '/inspection/my-issues'
  return '/feedback'
}

const verifyStoredAuthToken = async () => {
  const token = localStorage.getItem('auth_token')
  if (!isUsableAuthToken(token)) {
    clearAuthSession(token ? '登录已过期，请重新登录。' : '')
    return false
  }

  try {
    const response = await axios.get('/api/auth/me')
    storeAuthSession(response.data.user, response.data.token || token)
    return true
  } catch (error) {
    clearAuthSession(error?.response?.data?.error || '登录已过期，请重新登录。')
    return false
  }
}

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('auth_token')

  if (to.meta.public) {
    if (to.path === '/login' && token && (await verifyStoredAuthToken())) {
      const verifiedRole = localStorage.getItem('user_role')
      let verifiedPermissions = {}
      try {
        verifiedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
      } catch (error) {
        verifiedPermissions = {}
      }
      next(resolveFallbackPath(verifiedRole, verifiedPermissions))
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
  let verifiedPermissions = {}
  try {
    verifiedPermissions = JSON.parse(localStorage.getItem('permissions') || '{}')
  } catch (error) {
    verifiedPermissions = {}
  }

  if (!canAccessPath(to.path, verifiedRole, verifiedPermissions)) {
    next(resolveFallbackPath(verifiedRole, verifiedPermissions))
    return
  }

  next()
})

export default router
