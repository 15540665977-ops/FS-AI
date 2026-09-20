<template>
  <div class="page">

    <!-- 顶栏 -->
    <header class="topbar">
      <router-link to="/" class="back-link">← 返回分析</router-link>
      <span class="brand">跨材料对比</span>
    </header>

    <!-- 配置面板 -->
    <main class="body">
      <div class="config-panel">

        <!-- 左栏：参考材料选择 -->
        <div class="ref-panel">
          <div class="panel-title">参考材料（知识库）</div>
          <div class="type-row">
            <span class="field-label">测试类型：</span>
            <el-select v-model="specType" size="small" class="spec-sel">
              <el-option label="FTIR 红外" value="ftir" />
              <el-option label="DSC 热量" value="dsc" />
              <el-option label="TGA 热重" value="tga" />
            </el-select>
          </div>

          <div class="entries-list">
            <div
              v-for="e in entries"
              :key="e.id"
              class="entry-item"
              :class="{
                selected: selectedIds.includes(e.id),
                disabled: !selectedIds.includes(e.id) && selectedIds.length >= 5,
              }"
              @click="toggleEntry(e.id)"
            >
              <el-checkbox :model-value="selectedIds.includes(e.id)" @click.stop="toggleEntry(e.id)" />
              <span class="entry-id">{{ e.id }}</span>
              <span class="entry-label">{{ e.label }}</span>
            </div>
            <div v-if="entries.length === 0" class="entries-empty">加载中…</div>
          </div>
          <div class="hint-text">最多选 5 个（已选 {{ selectedIds.length }}）</div>
        </div>

        <!-- 右栏：待测样品上传 -->
        <div class="sample-panel">
          <div class="panel-title">待测样品</div>
          <div
            class="upload-area"
            :class="{ 'has-file': !!sampleFile }"
            @click="pickFile"
            @dragover.prevent
            @drop.prevent="onDrop"
          >
            <template v-if="!sampleFile">
              <el-icon class="up-icon"><Upload /></el-icon>
              <p class="up-text">点击或拖放上传谱图</p>
              <p class="up-hint">PNG / JPG / PDF</p>
            </template>
            <template v-else>
              <img v-if="samplePreview" :src="samplePreview" class="sample-thumb" @click.stop="lightbox = samplePreview" />
              <el-icon v-else class="file-icon"><Document /></el-icon>
              <span class="sample-name">{{ sampleFile.name }}</span>
              <el-icon class="rm-btn" @click.stop="removeSample"><Close /></el-icon>
            </template>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-row">
        <el-button
          type="primary"
          :disabled="!canSubmit || loading"
          :loading="loading"
          @click="submit"
        >
          开始对比分析
        </el-button>
        <el-button v-if="loading" type="danger" @click="abortStream">中止</el-button>
      </div>

      <!-- 分析结果 -->
      <div v-if="resultText || spectraData" class="result-section">
        <div class="result-label">── 分析结果 ──</div>
        <div class="ai-bubble">
          <div class="ai-content" v-html="render(resultText)" />
          <span v-if="streaming" class="cursor">▍</span>
          <SpectraCompare
            v-if="spectraData"
            :observed-peaks="spectraData.observed_peaks"
            :standard-materials="spectraData.standard_materials"
            :image-urls="spectraData.image_urls"
          />
        </div>
      </div>
    </main>

    <input ref="fileInput" type="file" accept=".png,.jpg,.jpeg,.pdf" style="display:none" @change="onFilePick" />

    <!-- 大图预览 -->
    <el-image-viewer v-if="lightbox" :url-list="[lightbox]" @close="lightbox = null" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Upload, Document, Close } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import SpectraCompare from '../components/SpectraCompare.vue'
import { apiFetch } from '../apiFetch'
import { apiUrl } from '../api'

marked.setOptions({ breaks: true, gfm: true })

// ── 状态 ─────────────────────────────────────────────
const entries       = ref([])
const selectedIds   = ref([])
const specType      = ref('ftir')
const sampleFile    = ref(null)
const samplePreview = ref(null)
const loading       = ref(false)
const streaming     = ref(false)
const resultText    = ref('')
const spectraData   = ref(null)
const lightbox      = ref(null)
const fileInput     = ref(null)
let   abortCtrl     = null

// ── 计算 ─────────────────────────────────────────────
const canSubmit = computed(() =>
  selectedIds.value.length >= 1 && !!sampleFile.value && !loading.value
)

// ── 工具 ─────────────────────────────────────────────
function render(text) {
  return text ? DOMPurify.sanitize(marked.parse(text)) : ''
}

// ── 知识库条目加载 ─────────────────────────────────────
async function loadEntries() {
  try {
    const r = await apiFetch('/api/v1/knowledge/entries')
    if (r.ok) entries.value = await r.json()
  } catch {}
}

// ── 材料选择 ─────────────────────────────────────────
function toggleEntry(id) {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) {
    selectedIds.value.splice(idx, 1)
  } else if (selectedIds.value.length < 5) {
    selectedIds.value.push(id)
  }
}

// ── 文件上传 ─────────────────────────────────────────
function pickFile() { fileInput.value?.click() }

function onFilePick(e) {
  const f = e.target.files[0]
  if (!f) return
  setSample(f)
  e.target.value = ''
}

function onDrop(e) {
  const f = e.dataTransfer.files[0]
  if (f) setSample(f)
}

function setSample(f) {
  if (samplePreview.value) URL.revokeObjectURL(samplePreview.value)
  sampleFile.value = f
  samplePreview.value = f.name.match(/\.(png|jpe?g|webp)$/i)
    ? URL.createObjectURL(f)
    : null
}

function removeSample() {
  if (samplePreview.value) URL.revokeObjectURL(samplePreview.value)
  sampleFile.value = null
  samplePreview.value = null
}

// ── 提交 ─────────────────────────────────────────────
async function submit() {
  if (!canSubmit.value) return

  resultText.value = ''
  spectraData.value = null
  loading.value = true
  streaming.value = true
  abortCtrl = new AbortController()

  const fd = new FormData()
  fd.append('file', sampleFile.value)
  fd.append('material_ids', JSON.stringify(selectedIds.value))
  fd.append('spec_type', specType.value)

  try {
    const resp = await apiFetch('/api/v1/chat/cross-compare', {
      method: 'POST',
      body: fd,
      signal: abortCtrl.signal,
    })
    if (!resp.ok) {
      resultText.value = `请求失败 (${resp.status})`
      return
    }

    const reader = resp.body.getReader()
    const dec = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const p = JSON.parse(line.slice(6))
          if (p.content) {
            resultText.value += p.content
          } else if (p.type === 'spectra_data' && p.mode === 'cross_compare') {
            spectraData.value = { ...p, image_urls: (p.image_urls || []).map(apiUrl) }
          } else if (p.done) {
            // analysis complete
          } else if (p.error) {
            resultText.value += `\n⚠️ ${p.error}`
          }
        } catch {}
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') resultText.value = `连接失败：${e.message}`
  } finally {
    loading.value = false
    streaming.value = false
  }
}

function abortStream() {
  abortCtrl?.abort()
}

// ── 初始化 ─────────────────────────────────────────────
onMounted(loadEntries)
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
</style>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #0f1320;
  color: #c8d3e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 48px;
  border-bottom: 1px solid #1e2840;
  background: #131929;
  flex-shrink: 0;
}
.back-link { color: #4d9cf5; font-size: 13px; text-decoration: none; }
.back-link:hover { color: #7ab8ff; }
.brand { font-size: 15px; font-weight: 700; color: #d0dff5; }

.body {
  flex: 1;
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-panel {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.ref-panel {
  flex: 1;
  border: 1px solid #1e2840;
  border-radius: 8px;
  background: #131929;
  overflow: hidden;
}

.panel-title {
  padding: 10px 14px;
  background: #0a1020;
  border-bottom: 1px solid #1e2840;
  font-size: 13px;
  font-weight: 600;
  color: #8ab4d8;
}

.type-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid #1e2840;
}
.field-label { font-size: 12px; color: #6b7fa3; white-space: nowrap; }
.spec-sel { width: 120px; }

.entries-list {
  max-height: 280px;
  overflow-y: auto;
  padding: 4px 0;
}
.entry-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: 13px;
  transition: background .15s;
}
.entry-item:hover { background: #1a2240; }
.entry-item.selected { background: #1a2d4e; }
.entry-item.disabled { opacity: 0.38; cursor: not-allowed; }
.entry-id { color: #4d9cf5; font-weight: 600; min-width: 52px; }
.entry-label { color: #8a9bb5; }
.entries-empty { padding: 20px; text-align: center; color: #3a4d6a; font-size: 12px; }

.hint-text {
  padding: 8px 14px;
  font-size: 11px;
  color: #4a5d7a;
  border-top: 1px solid #1e2840;
}

.sample-panel {
  width: 240px;
  flex-shrink: 0;
  border: 1px solid #1e2840;
  border-radius: 8px;
  background: #131929;
  overflow: hidden;
}

.upload-area {
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  padding: 16px;
  border: 2px dashed transparent;
  transition: border-color .2s;
}
.upload-area:hover, .upload-area.has-file { border-color: #2a3d5e; }
.up-icon { font-size: 32px; color: #2a3d5e; }
.up-text { font-size: 13px; color: #4a5d7a; }
.up-hint { font-size: 11px; color: #3a4d6a; }
.sample-thumb {
  width: 100%;
  max-height: 120px;
  object-fit: contain;
  border-radius: 4px;
  cursor: zoom-in;
}
.file-icon { font-size: 36px; color: #4d9cf5; }
.sample-name { font-size: 11px; color: #6a7d9a; text-align: center; word-break: break-all; }
.rm-btn { color: #5a6d8a; cursor: pointer; font-size: 16px; }
.rm-btn:hover { color: #e56; }

.action-row {
  display: flex;
  gap: 10px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-label {
  font-size: 12px;
  color: #3a4d6a;
  text-align: center;
}
.ai-bubble {
  background: #161d30;
  border: 1px solid #232f4a;
  border-radius: 12px;
  padding: 16px 18px;
  color: #c8d3e8;
  font-size: 14px;
  line-height: 1.75;
}
.cursor { color: #4d9cf5; animation: blink .7s steps(1) infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

:deep(.ai-content) { font-size: 14px; line-height: 1.75; color: #c8d3e8; }
:deep(.ai-content h1), :deep(.ai-content h2) {
  font-size: 15px; font-weight: 700; color: #d0dff5;
  margin: 14px 0 6px; padding-bottom: 4px; border-bottom: 1px solid #2a3550;
}
:deep(.ai-content h3) { font-size: 14px; font-weight: 600; color: #8ab4d8; margin: 10px 0 4px; }
:deep(.ai-content p)  { margin: 4px 0; }
:deep(.ai-content ul), :deep(.ai-content ol) { padding-left: 20px; margin: 4px 0; }
:deep(.ai-content li) { margin: 2px 0; }
:deep(.ai-content strong) { color: #d0dff5; font-weight: 600; }
:deep(.ai-content code) {
  background: #0f1320; border: 1px solid #2a3550; border-radius: 3px;
  padding: 1px 5px; font-size: 12px; color: #7ec8e3;
}
:deep(.ai-content table) { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 13px; }
:deep(.ai-content th) {
  background: #1a2640; color: #8ab4d8; font-weight: 600;
  padding: 6px 10px; border: 1px solid #2a3550; text-align: left;
}
:deep(.ai-content td) { padding: 5px 10px; border: 1px solid #1e2840; color: #b8c8e0; }
:deep(.ai-content tr:nth-child(even) td) { background: #111928; }
</style>
