import { createRouter, createWebHistory } from 'vue-router'
import FailureAnalysis from '../views/FailureAnalysis.vue'
import ConsistencyCheck from '../views/ConsistencyCheck.vue'
import StandardLibrary from '../views/StandardLibrary.vue'
import CaseRecords from '../views/CaseRecords.vue'

const routes = [
  { path: '/', redirect: '/failure-analysis' },
  { path: '/failure-analysis', component: FailureAnalysis, meta: { title: '失效分析' } },
  { path: '/consistency-check', component: ConsistencyCheck, meta: { title: '一致性检验' } },
  { path: '/standard-library', component: StandardLibrary, meta: { title: '标准谱图库' } },
  { path: '/case-records', component: CaseRecords, meta: { title: '案例记录' } },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
