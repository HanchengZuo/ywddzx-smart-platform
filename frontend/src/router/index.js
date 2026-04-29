import { createRouter, createWebHistory } from 'vue-router'
import InspectionStandardsView from '../views/inspection/InspectionStandardsView.vue'
import StationMapView from '../views/inspection/StationMapView.vue'

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
  if (path.startsWith('/management')) return false
  if (path === '/inspection/station-map') return hasPermission(role, permissions, 'view_station_map')
  if (path === '/inspection/register') return hasPermission(role, permissions, 'submit_inspections')
  if (path === '/inspection/standards') return hasPermission(role, permissions, 'view_inspection_standards')
  if (path === '/inspection/checklist-originals') return hasPermission(role, permissions, 'view_checklist_originals')
  if (path === '/inspection/issues') {
    return Boolean(permissions.view_all_inspection_issues || permissions.view_own_inspection_issues)
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
  if (role === 'supervisor') return '/inspection/my-issues'
  if (permissions.view_training_materials) return '/training/materials'
  return '/feedback'
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const role = localStorage.getItem('user_role')
  let permissions = {}
  try {
    permissions = JSON.parse(localStorage.getItem('permissions') || '{}')
  } catch (error) {
    permissions = {}
  }

  if (to.meta.public) {
    if (to.path === '/login' && token) {
      next(resolveFallbackPath(role, permissions))
      return
    }
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  if (!canAccessPath(to.path, role, permissions)) {
    next(resolveFallbackPath(role, permissions))
    return
  }

  next()
})

export default router
