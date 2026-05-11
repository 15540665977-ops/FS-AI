import { createRouter, createWebHistory } from 'vue-router'
import FailureAnalysis from '../views/FailureAnalysis.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: FailureAnalysis }],
})
