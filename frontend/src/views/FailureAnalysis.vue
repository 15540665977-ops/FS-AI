<template>
  <div class="page">

    <!-- ── 顶栏 ── -->
    <header class="topbar">
      <span class="brand">谱图分析</span>
      <el-button text size="small" class="history-btn" @click="drawerOpen = true">
        历史记录
      </el-button>
    </header>

    <!-- ── 主体 ── -->
    <main class="body">

      <!-- 欢迎态（没有任何消息时） -->
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">⬡</div>
        <p class="empty-title">上传谱图，开始分析</p>
        <p class="empty-sub">支持 FTIR / DSC / TGA，可同时上传多张</p>
      </div>

      <!-- 对话记录 -->
      <div v-else class="messages" ref="msgRef">
        <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">

          <!-- 用户 -->
          <template v-if="m.role === 'user'">
            <div class="msg-bubble user-bubble">
              <div v-if="m.previews.length" class="thumb-row">
                <img
                  v-for="(s, j) in m.previews" :key="j"
                  :src="s" class="thumb"
                  @click="lightbox = s"
                />
                <span v-if="m.pdfCount" class="pdf-badge">
                  + {{ m.pdfCount }} 份 PDF
                </span>
              </div>
              <p v-if="m.text" class="msg-text">{{ m.text }}</p>
              <el-tag v-if="m.type !== 'general'" size="small" type="info" class="type-tag">
                {{ TYPE_LABEL[m.type] }}
              </el-tag>
            </div>
          </template>

          <!-- AI -->
          <template v-else>
            <div class="msg-bubble ai-bubble">
              <div class="ai-content" v-html="render(m.content)"></div>
              <span v-if="m.streaming" class="cursor">▍</span>
              <div v-if="m.caseNo" class="case-no">已存档 · {{ m.caseNo }}</div>
            </div>
          </template>

        </div>
      </div>

    </main>

    <!-- ── 输入区 ── -->
    <footer class="inputbar">

      <!-- 已选文件预览行 -->
      <div v-if="fileEntries.length" class="file-row">
        <div v-for="(f, i) in fileEntries" :key="i" class="file-chip">
          <img v-if="f.preview" :src="f.preview" class="chip-img" />
          <el-icon v-else class="chip-icon"><Document /></el-icon>
          <span class="chip-name">{{ shortName(f.name) }}</span>
          <el-icon class="chip-rm" @click="removeFile(i)"><Close /></el-icon>
        </div>
        <div class="file-chip add-chip" @click="pickFiles">
          <el-icon><Plus /></el-icon>
        </div>
      </div>

      <!-- 输入行 -->
      <div class="input-row">
        <!-- 上传按钮 -->
        <el-tooltip content="上传谱图（PNG / JPG / PDF）" placement="top">
          <el-button class="upload-btn" circle @click="pickFiles">
            <el-icon><Paperclip /></el-icon>
          </el-button>
        </el-tooltip>

        <!-- 分析类型 -->
        <el-select v-model="analysisType" size="default" class="type-sel">
          <el-option label="通用分析" value="general" />
          <el-option label="失效分析" value="failure" />
          <el-option label="一致性检验" value="consistency" />
        </el-select>

        <!-- 文字输入 -->
        <el-input
          v-model="inputText"
          placeholder="材料信息、失效背景…（可选）"
          @keydown.enter.exact.prevent="submit"
          :disabled="loading"
          class="text-input"
        />

        <!-- 发送 / 中止 -->
        <el-button
          v-if="!loading"
          type="primary"
          circle
          :disabled="fileEntries.length === 0"
          @click="submit"
        >
          <el-icon><Position /></el-icon>
        </el-button>
        <el-button v-else type="danger" circle @click="abort">
          <el-icon><VideoPause /></el-icon>
        </el-button>
      </div>

      <input ref="fileInput" type="file" multiple accept=".png,.jpg,.jpeg,.pdf"
             style="display:none" @change="onFilePick" />
    </footer>

    <!-- ── 历史记录抽屉 ── -->
    <el-drawer v-model="drawerOpen" title="历史记录" size="360px" direction="rtl">
      <div class="history-list">
        <div v-for="c in cases" :key="c.id" class="history-item">
          <div class="hi-top">
            <span class="hi-no">{{ c.case_no }}</span>
            <el-tag size="small" :type="confTag(c.confidence_level)">{{ c.confidence_level || '—' }}</el-tag>
          </div>
          <div class="hi-mat">{{ c.material_name }}</div>
          <div class="hi-time">{{ fmtDate(c.created_at) }}</div>
          <div class="hi-conclusion">{{ (c.conclusion || '').slice(0, 80) }}{{ c.conclusion?.length > 80 ? '…' : '' }}</div>
        </div>
        <div v-if="cases.length === 0" class="hi-empty">暂无记录</div>
      </div>
    </el-drawer>

    <!-- 大图预览 -->
    <el-image-viewer v-if="lightbox" :url-list="[lightbox]" @close="lightbox = null" />
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Close, Plus, Paperclip, Position, VideoPause } from '@element-plus/icons-vue'

// ── 常量 ─────────────────────────────────────────────
const TYPE_LABEL = { general: '通用', failure: '失效分析', consistency: '一致性检验' }

// ── 状态 ─────────────────────────────────────────────
const messages    = ref([])
const fileEntries = ref([])   // { name, preview|null, raw }
const inputText   = ref('')
const analysisType = ref('general')
const loading     = ref(false)
const drawerOpen  = ref(false)
const cases       = ref([])
const lightbox    = ref(null)
const msgRef      = ref(null)
const fileInput   = ref(null)
let   abortCtrl   = null

// ── 工具 ─────────────────────────────────────────────
const shortName = n => n.length > 14 ? n.slice(0, 11) + '…' + n.slice(-3) : n
const fmtDate   = iso => iso ? new Date(iso).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' }) : ''
const confTag   = l => ({ high:'success', medium:'warning', low:'danger' }[l] || 'info')
const scroll    = () => nextTick(() => { if (msgRef.value) msgRef.value.scrollTop = msgRef.value.scrollHeight })

function render(text) {
  if (!text) return ''
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/【(.+?)】/g, '<strong class="sec">【$1】</strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br/>')
}

// ── 文件 ─────────────────────────────────────────────
function pickFiles() { fileInput.value?.click() }

function onFilePick(e) {
  Array.from(e.target.files).forEach(f => {
    fileEntries.value.push({
      name: f.name,
      raw:  f,
      preview: f.name.match(/\.(png|jpe?g|webp)$/i) ? URL.createObjectURL(f) : null,
    })
  })
  e.target.value = ''
}

function removeFile(i) {
  const f = fileEntries.value[i]
  if (f.preview) URL.revokeObjectURL(f.preview)
  fileEntries.value.splice(i, 1)
}

// ── 历史 ─────────────────────────────────────────────
async function loadCases() {
  try {
    const r = await fetch('/api/v1/cases/?limit=50')
    cases.value = (await r.json()).items || []
  } catch {}
}

// ── 提交 ─────────────────────────────────────────────
async function submit() {
  if (!fileEntries.value.length || loading.value) return

  // 用户消息
  messages.value.push({
    role: 'user',
    previews: fileEntries.value.map(f => f.preview).filter(Boolean),
    pdfCount: fileEntries.value.filter(f => !f.preview).length,
    text: inputText.value || null,
    type: analysisType.value,
  })

  // AI 占位
  const ai = { role: 'assistant', content: '', streaming: true, caseNo: null }
  messages.value.push(ai)
  scroll()

  // FormData
  const fd = new FormData()
  fileEntries.value.forEach(f => fd.append('files', f.raw))
  fd.append('analysis_type', analysisType.value)
  if (inputText.value) fd.append('failure_background', inputText.value)

  // 清空输入
  fileEntries.value = []
  inputText.value = ''

  loading.value = true
  abortCtrl = new AbortController()

  try {
    const resp = await fetch('/api/v1/chat/stream', { method:'POST', body:fd, signal:abortCtrl.signal })
    if (!resp.ok) { ai.content = `请求失败 (${resp.status})`; return }

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
          if (p.content)       { ai.content += p.content; scroll() }
          else if (p.done)     { ai.caseNo = p.case_no; loadCases() }
          else if (p.error)    { ai.content += `\n⚠️ ${p.error}` }
        } catch {}
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') ai.content = `连接失败：${e.message}`
  } finally {
    loading.value = false
    ai.streaming = false
    scroll()
  }
}

function abort() { abortCtrl?.abort(); loading.value = false }

onMounted(loadCases)
</script>

<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #app { height: 100%; background: #0f1320; color: #c8d3e8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
</style>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* ── 顶栏 ── */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 48px;
  border-bottom: 1px solid #1e2840;
  background: #131929;
  flex-shrink: 0;
}
.brand { font-size: 15px; font-weight: 700; color: #d0dff5; letter-spacing: 0.5px; }
.history-btn { color: #6a7d9a !important; }

/* ── 主体 ── */
.body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #4a5d7a;
}
.empty-icon  { font-size: 52px; color: #1e2840; }
.empty-title { font-size: 16px; color: #6a7d9a; }
.empty-sub   { font-size: 13px; }

.messages { padding: 0 max(24px, calc(50% - 420px)); display: flex; flex-direction: column; gap: 20px; }

.msg-row { display: flex; }
.msg-row.user      { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }

.msg-bubble {
  max-width: 76%;
  padding: 14px 18px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.75;
}

.user-bubble {
  background: #1e3a5f;
  border: 1px solid #2a4d7a;
  color: #d0dff5;
}

.ai-bubble {
  background: #161d30;
  border: 1px solid #232f4a;
  color: #c8d3e8;
}

.thumb-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; align-items: center; }
.thumb { width: 80px; height: 60px; object-fit: cover; border-radius: 6px; border: 1px solid #2a4d7a; cursor: zoom-in; }
.pdf-badge { font-size: 12px; color: #6a7d9a; }
.msg-text { white-space: pre-wrap; word-break: break-word; }
.type-tag { margin-top: 8px; }

.ai-content { white-space: pre-wrap; word-break: break-word; }
:deep(.sec) { color: #4d9cf5; display: block; margin: 10px 0 4px; font-size: 13px; }

.cursor { color: #4d9cf5; animation: blink .7s steps(1) infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

.case-no { margin-top: 10px; font-size: 12px; color: #3d6a9e; border-top: 1px solid #1e2840; padding-top: 8px; }

/* ── 输入区 ── */
.inputbar {
  border-top: 1px solid #1e2840;
  padding: 12px 20px 16px;
  background: #0f1320;
  flex-shrink: 0;
}

.file-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.file-chip {
  display: flex;
  align-items: center;
  gap: 5px;
  background: #1a2240;
  border: 1px solid #2a3550;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: #8a9bb5;
}
.chip-img  { width: 28px; height: 22px; object-fit: cover; border-radius: 3px; }
.chip-icon { font-size: 16px; color: #4d9cf5; }
.chip-rm   { cursor: pointer; color: #5a6d8a; margin-left: 2px; }
.chip-rm:hover { color: #e56; }
.add-chip  { cursor: pointer; padding: 4px 10px; border-style: dashed; }
.add-chip:hover { border-color: #4d9cf5; color: #4d9cf5; }

.input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.upload-btn { background: #1a2240 !important; border-color: #2a3550 !important; color: #8a9bb5 !important; }
.upload-btn:hover { border-color: #4d9cf5 !important; color: #4d9cf5 !important; }
.type-sel { width: 120px; }
.text-input { flex: 1; }

/* ── 历史抽屉 ── */
.history-list { display: flex; flex-direction: column; gap: 1px; }
.history-item { padding: 14px 0; border-bottom: 1px solid #1e2840; }
.hi-top  { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.hi-no   { font-size: 13px; font-weight: 600; color: #4d9cf5; }
.hi-mat  { font-size: 13px; color: #8a9bb5; }
.hi-time { font-size: 11px; color: #4a5d7a; margin-top: 2px; }
.hi-conclusion { font-size: 12px; color: #5a6d8a; margin-top: 6px; line-height: 1.5; }
.hi-empty { text-align: center; color: #3a4d6e; padding: 40px 0; font-size: 13px; }
</style>
