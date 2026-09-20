import { createRouter, createWebHashHistory } from 'vue-router'
import { auth, loadCurrentUser } from '../auth'
import FailureAnalysis from '../views/FailureAnalysis.vue'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
    { path: '/cross-compare', component: () => import('../views/CrossCompare.vue') },
    { path: '/admin/users', component: () => import('../views/AdminUsers.vue'), meta: { admin: true } },
    { path: '/:pathMatch(.*)*', component: FailureAnalysis },
  ],
})

router.beforeEach(async (to) => {
  if (!auth.loaded) await loadCurrentUser()
  if (!to.meta.public && !auth.user) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.user?.is_admin) return '/'
  if (to.path === '/login' && auth.user) return '/'
  return true
})

export default router
