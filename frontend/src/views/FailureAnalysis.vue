<template>
  <div class="page-layout">
    <!-- 左侧：历史案例 -->
    <aside class="history-panel">
      <div class="panel-header">
        <span>历史案例</span>
        <el-button size="small" text :icon="Refresh" @click="loadCases" />
      </div>
      <div class="case-list">
        <div
          v-for="c in cases"
          :key="c.id"
          class="case-item"
          @click="loadCase(c)"
        >
          <div class="case-no">{{ c.case_no }}</div>
          <div class="case-mat">{{ c.material_name }}</div>
          <div class="case-time">{{ formatDate(c.created_at) }}</div>
          <el-tag
            size="small"
            :type="confidenceType(c.confidence_level)"
            class="case-conf"
          >{{ c.confidence_level }}</el-tag>
        </div>
        <div v-if="cases.length === 0" class="empty-hint">暂无记录</div>
      </div>
    </aside>

    <!-- 右侧：主体 -->
    <div class="main-panel">
      <!-- 顶部：分析参数 -->
      <div class="params-bar">
        <el-select
          v-model="analysisType"
          size="small"
          style="width: 130px"
        >
          <el-option label="通用谱图分析" value="general" />
          <el-option label="失效分析" value="failure" />
          <el-option label="一致性检验" value="consistency" />
        </el-select>

        <el-input
          v-model="materialHint"
          size="small"
          placeholder="材料信息（如：PP-T20，选填）"
          style="width: 220px"
          clearable
        />

        <el-input
          v-model="failureBackground"
          size="small"
          placeholder="失效背景描述（选填）"
          style="flex: 1; min-width: 180px"
          clearable
        />
      </div>

      <!-- 对话区 -->
      <div ref="chatRef" class="chat-area">
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-icon">⬡</div>
          <h2>谱图智能分析系统</h2>
          <p>上传 FTIR / DSC / TGA 谱图，AI 自动识别特征峰位、热参数，推断材料类型与失效模式</p>
          <div class="welcome-tips">
            <div class="tip">
              <strong>支持格式</strong>
              <span>PNG · JPG · PDF（自动提取页面）</span>
            </div>
            <div class="tip">
              <strong>分析能力</strong>
              <span>材料鉴定 · 失效推断 · 一致性检验</span>
            </div>
            <div class="tip">
              <strong>输出规范</strong>
              <span>峰位波数 · 置信度 · 知识来源</span>
            </div>
          </div>
        </div>

        <ChatMessage
          v-for="(msg, i) in messages"
          :key="i"
          :message="msg"
          @preview-image="openImagePreview"
        />
      </div>

      <!-- 底部：上传 + 发送 -->
      <div class="input-area">
        <FileUpload
          ref="uploadRef"
          v-model="selectedFiles"
          class="upload-area"
        />
        <div class="send-row">
          <el-input
            v-model="extraText"
            size="default"
            placeholder="可输入补充说明（可选）"
            @keydown.enter.exact.prevent="submit"
          />
          <el-button
            type="primary"
            :loading="loading"
            :disabled="selectedFiles.length === 0"
            @click="submit"
          >
            <el-icon v-if="!loading"><Position /></el-icon>
            {{ loading ? '分析中…' : '开始分析' }}
          </el-button>
          <el-button
            v-if="loading"
            type="danger"
            plain
            @click="abort"
          >中止</el-button>
        </div>
      </div>
    </div>
  </div>

  <!-- 图片大图预览 -->
  <el-image-viewer
    v-if="previewSrc"
    :url-list="[previewSrc]"
    @close="previewSrc = null"
  />
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Position, Refresh } from '@element-plus/icons-vue'
import FileUpload from '../components/FileUpload.vue'
import ChatMessage from '../components/ChatMessage.vue'

// ── 状态 ──────────────────────────────────────────────
const analysisType = ref('general')
const materialHint = ref('')
const failureBackground = ref('')
const extraText = ref('')
const selectedFiles = ref([])
const messages = ref([])
const cases = ref([])
const loading = ref(false)
const chatRef = ref(null)
const uploadRef = ref(null)
const previewSrc = ref(null)

let abortCtrl = null

// ── 工具函数 ──────────────────────────────────────────
function scrollToBottom() {
  nextTick(() => {
    if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
  })
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function confidenceType(level) {
  return { high: 'success', medium: 'warning', low: 'danger' }[level] || 'info'
}

function openImagePreview(src) {
  previewSrc.value = src
}

// ── 加载历史案例 ──────────────────────────────────────
async function loadCases() {
  try {
    const res = await fetch('/api/v1/cases/?limit=30')
    const data = await res.json()
    cases.value = data.items || []
  } catch {
    // 后端未启动时静默
  }
}

function loadCase(c) {
  try {
    const result = JSON.parse(c.analysis_result || '{}')
    ElMessage.info(`案例 ${c.case_no} — ${c.material_name}`)
  } catch { /* noop */ }
}

// ── 核心：提交分析 ────────────────────────────────────
async function submit() {
  if (selectedFiles.value.length === 0 || loading.value) return

  // 生成用户消息预览
  const previews = selectedFiles.value.map(f => {
    const isPdf = f.name?.toLowerCase().endsWith('.pdf')
    return isPdf ? null : URL.createObjectURL(f)
  }).filter(Boolean)

  const userMsg = {
    role: 'user',
    previews,
    text: extraText.value || null,
    meta: {
      analysisType: analysisType.value,
      materialHint: materialHint.value || null,
    },
  }
  messages.value.push(userMsg)

  // 占位 AI 消息
  const aiMsg = { role: 'assistant', content: '', streaming: true, caseNo: null }
  messages.value.push(aiMsg)
  scrollToBottom()

  // 构建 FormData
  const form = new FormData()
  selectedFiles.value.forEach(f => form.append('files', f))
  form.append('analysis_type', analysisType.value)
  if (materialHint.value) form.append('material_hint', materialHint.value)
  if (failureBackground.value) form.append('failure_background', failureBackground.value)
  if (extraText.value) form.append('failure_background',
    (failureBackground.value ? failureBackground.value + '\n' : '') + extraText.value)

  // 清空输入
  uploadRef.value?.clear()
  extraText.value = ''

  // 发起 SSE 请求
  loading.value = true
  abortCtrl = new AbortController()

  try {
    const resp = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      body: form,
      signal: abortCtrl.signal,
    })

    if (!resp.ok) {
      const err = await resp.text()
      aiMsg.content = `请求失败（${resp.status}）：${err}`
      aiMsg.streaming = false
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() // 保留不完整行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const payload = JSON.parse(line.slice(6))
          if (payload.content) {
            aiMsg.content += payload.content
            scrollToBottom()
          } else if (payload.done) {
            aiMsg.streaming = false
            aiMsg.caseNo = payload.case_no
          } else if (payload.error) {
            aiMsg.content += `\n\n⚠️ 错误：${payload.error}`
            aiMsg.streaming = false
          }
        } catch { /* 非 JSON 行忽略 */ }
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      aiMsg.content = `连接失败：${err.message}\n\n请确认后端服务已在 http://localhost:8000 启动。`
    }
    aiMsg.streaming = false
  } finally {
    loading.value = false
    aiMsg.streaming = false
    scrollToBottom()
  }
}

function abort() {
  abortCtrl?.abort()
  loading.value = false
}

onMounted(loadCases)
</script>

<style scoped>
.page-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ── 左侧历史面板 ── */
.history-panel {
  width: 200px;
  flex-shrink: 0;
  background: #131929;
  border-right: 1px solid #1e2840;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px 12px 10px;
  font-size: 13px;
  font-weight: 600;
  color: #6a7d9a;
  letter-spacing: 0.5px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #1e2840;
}

.case-list { overflow-y: auto; flex: 1; padding: 8px 0; }

.case-item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #1e2840;
  transition: background 0.15s;
}

.case-item:hover { background: #1a2240; }

.case-no { font-size: 12px; color: #4d9cf5; font-weight: 600; }
.case-mat { font-size: 12px; color: #8a9bb5; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.case-time { font-size: 11px; color: #4a5d7a; margin-top: 2px; }
.case-conf { margin-top: 4px; }
.empty-hint { text-align: center; color: #3a4d6e; font-size: 12px; padding: 24px; }

/* ── 右侧主区域 ── */
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.params-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: #131929;
  border-bottom: 1px solid #1e2840;
  flex-wrap: wrap;
}

/* ── 对话区 ── */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 12px;
}

.welcome {
  text-align: center;
  padding: 60px 40px;
}

.welcome-icon { font-size: 48px; color: #4d9cf5; margin-bottom: 16px; }
.welcome h2 { font-size: 22px; color: #d0dff5; margin-bottom: 10px; }
.welcome p { color: #6a7d9a; font-size: 14px; max-width: 480px; margin: 0 auto 32px; line-height: 1.7; }

.welcome-tips {
  display: flex;
  gap: 20px;
  justify-content: center;
  flex-wrap: wrap;
}

.tip {
  background: #151b2e;
  border: 1px solid #2a3550;
  border-radius: 8px;
  padding: 14px 20px;
  min-width: 160px;
  text-align: left;
}

.tip strong { display: block; color: #4d9cf5; font-size: 13px; margin-bottom: 4px; }
.tip span { font-size: 12px; color: #6a7d9a; }

/* ── 底部输入区 ── */
.input-area {
  border-top: 1px solid #1e2840;
  padding: 16px 20px;
  background: #0f1320;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.upload-area { width: 100%; }

.send-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.send-row .el-input { flex: 1; }
</style>
