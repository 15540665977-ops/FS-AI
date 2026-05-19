<template>
  <div class="sc-card">

    <!-- 顶部：材料选择器 + 图例 -->
    <div class="sc-header">
      <span class="sc-label">标准谱图：</span>
      <el-select
        v-model="selectedId"
        filterable
        clearable
        placeholder="选择标准材料"
        size="small"
        class="sc-sel"
        @change="onMaterialChange"
      >
        <el-option
          v-for="e in entries"
          :key="e.id"
          :label="`${e.id}  ${e.label}`"
          :value="e.id"
        />
      </el-select>
      <div class="sc-legend">
        <span class="leg-std">━━ 标准</span>
        <span class="leg-obs">┃ 观测峰</span>
      </div>
    </div>

    <!-- 图表区域：图像背景 + Canvas 前景 -->
    <div class="sc-wrap" ref="wrapRef">
      <img
        v-if="currentImageUrl && !imgError"
        :src="currentImageUrl"
        class="sc-bg"
        @load="onImgLoad"
        @error="imgError = true"
      />
      <div v-else class="sc-placeholder">{{ imgError ? '图像加载失败' : '无图像' }}</div>
      <canvas
        ref="canvasRef"
        class="sc-canvas"
        @mousemove="onMouseMove"
        @mouseleave="ttVisible = false"
      />
      <!-- Hover Tooltip -->
      <div v-show="ttVisible" class="sc-tt" :style="ttStyle">
        <span class="tt-wn">{{ ttData.wavenumber }} cm⁻¹</span>
        <span class="tt-asgn">{{ ttData.assignment }}</span>
        <span class="tt-int">强度：{{ ttData.intensity }}</span>
        <span class="tt-src" :class="ttData.source === 'observed' ? 'src-obs' : 'src-std'">
          {{ ttData.source === 'observed' ? '观测峰' : `标准 (${selectedId})` }}
        </span>
      </div>
    </div>

    <!-- 多图切换（仅多张图时显示） -->
    <div v-if="imageUrls.length > 1" class="sc-switcher">
      <button
        v-for="(_, i) in imageUrls"
        :key="i"
        :class="['sc-sw-btn', { active: currentImgIdx === i }]"
        @click="switchImage(i)"
      >
        图{{ i + 1 }}
      </button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  observedPeaks:     { type: Array,  default: () => [] },
  suggestedMaterial: { type: String, default: null },
  imageUrls:         { type: Array,  default: () => [] },
})

// ── 坐标边距（匹配主流 FTIR 软件报告图布局） ────────────────────
const LEFT_M   = 0.10
const RIGHT_M  = 0.04
const TOP_M    = 0.06
const BOTTOM_M = 0.14

// ── 高斯合成振幅映射（与 IRViewer 保持一致） ───────────────────
const FTIR_AMP = { '极强': 95, '很强': 85, '强': 60, '中': 35, '弱': 18, '很弱': 10 }

// ── 状态 ────────────────────────────────────────────────────────
const entries       = ref([])
const selectedId    = ref(props.suggestedMaterial)
const standardPeaks = ref([])
const currentImgIdx = ref(0)
const imgError      = ref(false)
const wrapRef       = ref(null)
const canvasRef     = ref(null)

// ── Tooltip 状态 ────────────────────────────────────────────────
const ttVisible = ref(false)
const ttData    = ref({ wavenumber: 0, assignment: '', intensity: '', source: 'standard' })
const ttStyle   = ref({})

// ── 当前显示的图像 URL ──────────────────────────────────────────
const currentImageUrl = computed(() => props.imageUrls[currentImgIdx.value] ?? null)

// ── 加载知识库条目列表（供下拉选择） ───────────────────────────
async function loadEntries() {
  try {
    const r = await fetch('/api/v1/knowledge/entries')
    entries.value = await r.json()
  } catch { /* 网络失败静默 */ }
}

// ── 加载选定材料的标准峰位并重绘 ───────────────────────────────
async function loadStandardPeaks(id) {
  if (!id) { standardPeaks.value = []; redraw(); return }
  try {
    const r = await fetch(`/api/v1/knowledge/entry/${id}`)
    const d = await r.json()
    standardPeaks.value = d.ftir_peaks || []
  } catch {
    standardPeaks.value = []
  }
  redraw()
}

function onMaterialChange(id) {
  loadStandardPeaks(id)
}

// ── 波数 ↔ Canvas X 坐标互换（4000 在左，400 在右） ─────────────
function wnToX(wn, W) {
  const plotW = W * (1 - LEFT_M - RIGHT_M)
  const plotX = W * LEFT_M
  return plotX + ((4000 - wn) / (4000 - 400)) * plotW
}

function xToWn(x, W) {
  const plotW = W * (1 - LEFT_M - RIGHT_M)
  const plotX = W * LEFT_M
  return 4000 - ((x - plotX) / plotW) * (4000 - 400)
}

// ── 重绘 Canvas 叠加层 ──────────────────────────────────────────
function redraw() {
  const canvas = canvasRef.value
  const wrap   = wrapRef.value
  if (!canvas || !wrap) return

  canvas.width  = wrap.clientWidth
  canvas.height = wrap.clientHeight

  const ctx   = canvas.getContext('2d')
  const W     = canvas.width
  const H     = canvas.height
  ctx.clearRect(0, 0, W, H)

  const plotH  = H * (1 - TOP_M - BOTTOM_M)
  const plotY0 = H * TOP_M   // 透过率 100% 对应的 Y 像素

  // 绘制标准谱图（高斯合成曲线，蓝色半透明）
  if (standardPeaks.value.length) {
    const wavenumbers = []
    for (let v = 4000; v >= 400; v -= 4) wavenumbers.push(v)

    const transmittances = wavenumbers.map(wn => {
      let absorbance = 0
      for (const p of standardPeaks.value) {
        absorbance += (FTIR_AMP[p.intensity] ?? 40) *
          Math.exp(-((wn - p.wavenumber) ** 2) / (2 * 18 ** 2))
      }
      return Math.max(0, 100 - absorbance)
    })

    ctx.beginPath()
    ctx.strokeStyle = 'rgba(77, 156, 245, 0.75)'
    ctx.lineWidth   = 1.5
    wavenumbers.forEach((wn, i) => {
      const cx = wnToX(wn, W)
      const cy = plotY0 + (1 - transmittances[i] / 100) * plotH
      i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy)
    })
    ctx.stroke()
  }

  // 绘制观测峰（橙色竖虚线）
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.85)'
  ctx.lineWidth   = 1.5
  ctx.setLineDash([4, 3])
  for (const p of props.observedPeaks) {
    const cx = wnToX(p.wavenumber, W)
    ctx.beginPath()
    ctx.moveTo(cx, H * TOP_M)
    ctx.lineTo(cx, H * (1 - BOTTOM_M))
    ctx.stroke()
  }
  ctx.setLineDash([])
}

// ── 图像加载完成后调整 canvas 尺寸并重绘 ────────────────────────
function onImgLoad() {
  nextTick(redraw)
}

// ── 切换图像 ────────────────────────────────────────────────────
function switchImage(i) {
  currentImgIdx.value = i
  imgError.value = false
  nextTick(redraw)
}

// ── 鼠标悬停检测 ────────────────────────────────────────────────
function onMouseMove(e) {
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const mx   = (e.clientX - rect.left) * (canvas.width / rect.width)
  const wn   = xToWn(mx, canvas.width)

  if (wn < 400 || wn > 4000) { ttVisible.value = false; return }

  let nearest = null
  let minDist = 60
  let src = ''

  for (const p of props.observedPeaks) {
    const d = Math.abs(p.wavenumber - wn)
    if (d < minDist) { minDist = d; nearest = p; src = 'observed' }
  }
  for (const p of standardPeaks.value) {
    const d = Math.abs(p.wavenumber - wn)
    if (d < minDist) { minDist = d; nearest = p; src = 'standard' }
  }

  if (nearest) {
    ttVisible.value = true
    ttData.value = { ...nearest, source: src }
    const rx  = e.clientX - rect.left
    const ry  = e.clientY - rect.top
    const ttX = Math.min(rx + 14, rect.width - 210)
    const ttY = Math.max(ry - 72, 4)
    ttStyle.value = { left: ttX + 'px', top: ttY + 'px' }
  } else {
    ttVisible.value = false
  }
}

// ── 初始化 ───────────────────────────────────────────────────────
onMounted(async () => {
  await loadEntries()
  if (selectedId.value) {
    await loadStandardPeaks(selectedId.value)
  }
})
</script>

<style scoped>
.sc-card {
  margin-top: 12px;
  border: 1px solid #1e2d4a;
  border-radius: 8px;
  background: #0d1628;
  overflow: hidden;
}

.sc-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #1e2d4a;
  background: #0a1020;
}

.sc-label { color: #6b7fa3; font-size: 12px; white-space: nowrap; }

.sc-sel { width: 200px; }

.sc-legend {
  margin-left: auto;
  display: flex;
  gap: 12px;
  font-size: 11px;
}
.leg-std { color: rgba(77, 156, 245, 0.9); }
.leg-obs { color: rgba(245, 158, 11, 0.9); }

/* 图表容器：图像撑开高度，canvas 绝对定位覆盖 */
.sc-wrap {
  position: relative;
  width: 100%;
  min-height: 60px;
  background: #0d1628;
}

.sc-bg {
  display: block;
  width: 100%;
  height: auto;
}

.sc-placeholder {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #3a4d6a;
  font-size: 13px;
}

.sc-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
}

/* Tooltip */
.sc-tt {
  position: absolute;
  background: rgba(10, 16, 32, 0.92);
  border: 1px solid #2a3d5e;
  border-radius: 6px;
  padding: 6px 10px;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 160px;
  z-index: 10;
}
.tt-wn   { color: #e0eaff; font-size: 13px; font-weight: 600; }
.tt-asgn { color: #9ab0d0; font-size: 11px; }
.tt-int  { color: #6b7fa3; font-size: 11px; }
.tt-src  { font-size: 10px; margin-top: 2px; }
.src-obs { color: rgba(245, 158, 11, 0.9); }
.src-std { color: rgba(77, 156, 245, 0.85); }

/* 多图切换 */
.sc-switcher {
  display: flex;
  gap: 6px;
  padding: 6px 12px;
  border-top: 1px solid #1e2d4a;
}
.sc-sw-btn {
  padding: 2px 10px;
  border-radius: 4px;
  border: 1px solid #2a3d5e;
  background: transparent;
  color: #6b7fa3;
  font-size: 11px;
  cursor: pointer;
}
.sc-sw-btn.active {
  background: #1a2d4e;
  border-color: #4d9cf5;
  color: #4d9cf5;
}
</style>
