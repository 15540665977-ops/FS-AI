<template>
  <div class="page">
    <div class="page-title">案例记录</div>
    <div class="filters">
      <el-input v-model="search" placeholder="按材料名 / 案例号搜索" :prefix-icon="Search"
        clearable style="width: 260px" @input="load" @clear="load" />
      <el-select v-model="confFilter" clearable placeholder="置信度" style="width: 120px" @change="load">
        <el-option label="高" value="high" />
        <el-option label="中" value="medium" />
        <el-option label="低" value="low" />
      </el-select>
      <span class="total-hint">共 {{ total }} 条记录</span>
    </div>

    <el-table :data="items" stripe border style="width: 100%" v-loading="loading"
      row-class-name="table-row" @row-click="viewDetail">
      <el-table-column prop="case_no" label="案例编号" width="130" />
      <el-table-column prop="material_name" label="材料" width="130" />
      <el-table-column prop="failure_description" label="分析类型" width="110" />
      <el-table-column prop="confidence_level" label="置信度" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="confType(row.confidence_level)">
            {{ confLabel(row.confidence_level) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="150">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="结论摘要" min-width="220">
        <template #default="{ row }">
          <span class="conclusion-text">
            {{ (row.conclusion || '').slice(0, 90) }}{{ (row.conclusion?.length || 0) > 90 ? '…' : '' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="" width="60" align="center">
        <template #default>
          <span class="row-hint">点击查看</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination v-if="total > pageSize" class="pagination" background
      layout="prev, pager, next" :total="total" :page-size="pageSize" :current-page="page"
      @current-change="p => { page = p; load() }" />

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="current ? `${current.case_no} — ${current.material_name}` : ''"
      width="72%"
      top="5vh"
      destroy-on-close
      class="case-dialog"
    >
      <div v-if="current" class="dialog-body">
        <!-- 基本信息 -->
        <div class="meta-bar">
          <div class="meta-item">
            <span class="meta-label">分析类型</span>
            <span class="meta-val">{{ current.failure_description || '—' }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">置信度</span>
            <el-tag size="small" :type="confType(current.confidence_level)">
              {{ confLabel(current.confidence_level) }}
            </el-tag>
          </div>
          <div class="meta-item">
            <span class="meta-label">上传文件</span>
            <span class="meta-val file-list">{{ fileNames(current.uploaded_files) }}</span>
          </div>
          <div class="meta-item">
            <span class="meta-label">分析时间</span>
            <span class="meta-val">{{ fmt(current.created_at) }}</span>
          </div>
        </div>

        <el-divider />

        <!-- 完整分析报告 -->
        <div class="report-title">完整分析报告</div>
        <div v-if="current.analysis_result"
          class="report-content"
          v-html="renderMd(current.analysis_result)" />
        <el-empty v-else description="暂无分析内容" />
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="copyReport">复制报告</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { apiFetch } from '../apiFetch'

const items      = ref([])
const total      = ref(0)
const page       = ref(1)
const pageSize   = 20
const search     = ref('')
const confFilter = ref('')
const loading    = ref(false)
const dialogVisible = ref(false)
const current    = ref(null)

const CONF_TYPE  = { high: 'success', medium: 'warning', low: 'danger' }
const CONF_LABEL = { high: '高', medium: '中', low: '低', unknown: '未知' }
function confType(l)  { return CONF_TYPE[l] || 'info' }
function confLabel(l) { return CONF_LABEL[l] || (l || '—') }
function fmt(iso)     { return iso ? new Date(iso).toLocaleString('zh-CN') : '—' }
function renderMd(t)  { return DOMPurify.sanitize(marked.parse(t || '')) }

function fileNames(json) {
  try {
    const arr = JSON.parse(json || '[]')
    if (!arr.length) return '—'
    // 兼容旧记录中存的完整路径，只取文件名部分
    return arr.map(p => p.replace(/.*[/\\]/, '')).join('、')
  } catch { return json || '—' }
}

async function load() {
  loading.value = true
  try {
    const p = new URLSearchParams({ limit: pageSize, offset: (page.value - 1) * pageSize })
    if (search.value)  p.append('q', search.value)
    if (confFilter.value) p.append('confidence_level', confFilter.value)
    const res  = await apiFetch(`/api/v1/cases/?${p}`)
    const data = await res.json()
    items.value = data.items || []
    total.value = data.total || 0
  } catch { /* noop */ } finally { loading.value = false }
}

function viewDetail(row) {
  current.value = row
  dialogVisible.value = true
}

async function copyReport() {
  try {
    await navigator.clipboard.writeText(current.value?.analysis_result || '')
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选中文本复制')
  }
}

onMounted(load)
</script>

<style scoped>
.page       { padding: 28px; }
.page-title { font-size: 20px; font-weight: 600; color: #d0dff5; margin-bottom: 20px; }
.filters    { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.total-hint { color: #5a6a85; font-size: 13px; margin-left: 4px; }
.conclusion-text { color: #8a9bb5; font-size: 12px; }
.row-hint   { color: #3a6a9a; font-size: 11px; }
.pagination { margin-top: 20px; justify-content: flex-end; }

/* 行可点击样式 */
:deep(.table-row) { cursor: pointer; }
:deep(.table-row:hover td) { background: #1e2d45 !important; }

/* 弹窗内容 */
.dialog-body  { max-height: 78vh; overflow-y: auto; padding: 0 4px; }

.meta-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 40px;
  background: #141e35;
  border: 1px solid #243050;
  border-radius: 8px;
  padding: 14px 20px;
  margin-bottom: 4px;
}
.meta-item   { display: flex; align-items: flex-start; gap: 8px; }
.meta-label  { color: #5a7090; font-size: 12px; white-space: nowrap; padding-top: 2px; }
.meta-val    { color: #c8d8f0; font-size: 13px; }
.file-list   { color: #7eb8f7; }

.report-title {
  font-size: 14px;
  font-weight: 600;
  color: #a0b8d8;
  margin: 4px 0 12px;
}
.report-content {
  font-size: 13.5px;
  color: #c8d3e8;
  line-height: 1.85;
  background: #111928;
  padding: 20px 24px;
  border-radius: 8px;
  border: 1px solid #1e2d48;
  overflow-x: auto;
}
.report-content :deep(h1),
.report-content :deep(h2),
.report-content :deep(h3) {
  color: #7eb8f7;
  margin: 20px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #1e3050;
}
.report-content :deep(h1) { font-size: 16px; }
.report-content :deep(h2) { font-size: 15px; }
.report-content :deep(h3) { font-size: 14px; }
.report-content :deep(strong) { color: #e8f0fc; }
.report-content :deep(em)     { color: #a0c4e8; }
.report-content :deep(hr)     { border-color: #1e3050; margin: 16px 0; }
.report-content :deep(code)   {
  background: #1e2d48; padding: 1px 6px;
  border-radius: 3px; font-size: 12px; color: #7ec8f7;
}
.report-content :deep(pre) {
  background: #0d1525; padding: 14px; border-radius: 6px;
  overflow-x: auto; border: 1px solid #1a2a40;
}
.report-content :deep(table) {
  border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px;
}
.report-content :deep(th),
.report-content :deep(td) {
  border: 1px solid #253550; padding: 7px 12px; text-align: left;
}
.report-content :deep(th)     { background: #1a2d48; color: #9ab8d8; font-weight: 600; }
.report-content :deep(tr:hover td) { background: #162038; }
.report-content :deep(ul),
.report-content :deep(ol)     { padding-left: 22px; margin: 6px 0; }
.report-content :deep(li)     { margin: 3px 0; }
.report-content :deep(blockquote) {
  border-left: 3px solid #3a6090; margin: 8px 0;
  padding: 6px 14px; background: #141e35; color: #90a8c8;
}
</style>
