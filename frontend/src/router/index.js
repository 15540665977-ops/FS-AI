import { createRouter, createWebHistory } from 'vue-router'
import FailureAnalysis from '../views/FailureAnalysis.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/cross-compare', component: () => import('../views/CrossCompare.vue') },
    { path: '/:pathMatch(.*)*', component: FailureAnalysis },
  ],
})
