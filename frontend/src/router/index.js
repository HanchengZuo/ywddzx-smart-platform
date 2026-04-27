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

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const role = localStorage.getItem('user_role')

  if (to.meta.public) {
    if (to.path === '/login' && token) {
      next('/inspection/issues')
      return
    }
    next()
    return
  }

  if (!token) {
    next('/login')
    return
  }

  next()
})

export default router
