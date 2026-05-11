<template>
  <div class="page">
    <div class="page-title">案例记录</div>
    <div class="filters">
      <el-input v-model="search" placeholder="按材料名 / 案例号搜索" :prefix-icon="Search" clearable style="width: 260px" @input="load" />
      <el-select v-model="confFilter" clearable placeholder="置信度" style="width: 120px" @change="load">
        <el-option label="高" value="high" />
        <el-option label="中" value="medium" />
        <el-option label="低" value="low" />
      </el-select>
    </div>

    <el-table :data="items" stripe border style="width: 100%" v-loading="loading">
      <el-table-column prop="case_no" label="案例编号" width="130" />
      <el-table-column prop="material_name" label="材料" width="120" />
      <el-table-column prop="failure_description" label="分析类型" width="140" />
      <el-table-column prop="confidence_level" label="置信度" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="confType(row.confidence_level)">{{ row.confidence_level || '—' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="日期" width="140">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="摘要" min-width="200">
        <template #default="{ row }">
          <span class="conclusion">{{ (row.conclusion || '').slice(0, 80) }}{{ row.conclusion?.length > 80 ? '…' : '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="viewDetail(row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > pageSize"
      class="pagination"
      background
      layout="prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="p => { page = p; load() }"
    />

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="`案例详情 — ${current?.case_no}`" size="50%">
      <div v-if="current" class="detail-content">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="材料">{{ current.material_name }}</el-descriptions-item>
          <el-descriptions-item label="置信度">
            <el-tag :type="confType(current.confidence_level)" size="small">{{ current.confidence_level }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分析类型" :span="2">{{ current.failure_description }}</el-descriptions-item>
          <el-descriptions-item label="日期" :span="2">{{ fmt(current.created_at) }}</el-descriptions-item>
        </el-descriptions>
        <div class="result-text">{{ current.analysis_result }}</div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const confFilter = ref('')
const loading = ref(false)
const drawerVisible = ref(false)
const current = ref(null)

function confType(l) { return { high: 'success', medium: 'warning', low: 'danger' }[l] || 'info' }
function fmt(iso) { return iso ? new Date(iso).toLocaleString('zh-CN') : '—' }

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({ limit: pageSize, offset: (page.value - 1) * pageSize })
    if (search.value) params.append('q', search.value)
    if (confFilter.value) params.append('confidence_level', confFilter.value)
    const res = await fetch(`/api/v1/cases/?${params}`)
    const data = await res.json()
    items.value = data.items || []
    total.value = data.total || 0
  } catch { /* noop */ } finally { loading.value = false }
}

function viewDetail(row) { current.value = row; drawerVisible.value = true }

onMounted(load)
</script>

<style scoped>
.page { padding: 28px; }
.page-title { font-size: 20px; font-weight: 600; color: #d0dff5; margin-bottom: 20px; }
.filters { display: flex; gap: 12px; margin-bottom: 16px; }
.conclusion { color: #8a9bb5; font-size: 12px; }
.pagination { margin-top: 20px; justify-content: flex-end; }
.detail-content { padding: 8px; }
.result-text { margin-top: 16px; font-size: 13px; color: #c8d3e8; white-space: pre-wrap; line-height: 1.7; background: #1a2240; padding: 16px; border-radius: 8px; border: 1px solid #2a3550; }
</style>
