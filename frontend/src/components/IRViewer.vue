<template>
  <!-- ── 知识库抽屉：分类菜单 ── -->
  <el-drawer
    v-model="open"
    title="知识库"
    size="300px"
    direction="rtl"
    :destroy-on-close="false"
    class="kb-drawer"
  >
    <div class="kb-menu">
      <div v-for="cat in tree" :key="cat.super" class="cat-block">

        <!-- 大类标题（可点击展开/收起） -->
        <div class="cat-head" @click="toggle(cat.super)">
          <span class="cat-name">{{ cat.super }}</span>
          <span class="cat-arrow" :class="{ open: expanded.has(cat.super) }">▶</span>
        </div>

        <!-- 子类 + 材料 -->
        <div v-show="expanded.has(cat.super)" class="cat-body">
          <div v-for="sub in cat.subs" :key="sub.group" class="sub-block">
            <div class="sub-name">{{ sub.group }}</div>
            <div
              v-for="item in sub.items"
              :key="item.id"
              class="mat-link"
              @click="openMaterial(item.id)"
            >
              <span class="mat-link-id">{{ item.id }}</span>
              <span class="mat-link-label">{{ item.label }}</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  </el-drawer>

  <!-- ── 材料详情弹窗 ── -->
  <el-dialog
    v-model="dlgOpen"
    :title="dlgTitle"
    width="840px"
    :destroy-on-close="true"
    class="mat-dlg"
    @opened="drawCharts"
    @closed="destroyCharts"
  >
    <div v-if="dlgData" class="dlg-body">

      <!-- 标签行 -->
      <div class="dlg-tags">
        <el-tag size="small" type="info">{{ dlgData.super_group }}</el-tag>
        <el-tag size="small" style="margin-left:4px">{{ dlgData.display_group }}</el-tag>
        <span class="dlg-aliases">{{ dlgData.common_names?.slice(1).join(' / ') }}</span>
      </div>

      <!-- FTIR -->
      <div class="chart-label">FTIR 红外谱图</div>
      <div class="chart-box chart-wide ftir-wrap" @mouseleave="ttVisible = false">
        <canvas ref="cvFtir" />
        <div v-show="ttVisible" class="ftir-tt" :style="ttStyle">
          <span class="tt-wn">{{ ttData.wavenumber }} cm⁻¹</span>
          <span class="tt-asgn">{{ ttData.assignment }}</span>
          <span class="tt-int" :class="ic(ttData.intensity)">强度：{{ ttData.intensity }}</span>
        </div>
      </div>

      <!-- DSC + TGA -->
      <div class="row2">
        <div class="half">
          <div class="chart-label">DSC 曲线</div>
          <div class="chart-box">
            <canvas ref="cvDsc" />
          </div>
          <!-- DSC 特征参数 -->
          <table v-if="dlgData.dsc_features?.length" class="feat-tbl" style="margin-top:8px">
            <thead><tr><th>参数</th><th>典型值</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="f in dlgData.dsc_features" :key="f.parameter">
                <td class="feat-param">{{ f.parameter }}</td>
                <td class="feat-val">{{ f.value }}</td>
                <td class="feat-note">{{ f.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="half">
          <div class="chart-label">TGA 曲线</div>
          <div class="chart-box">
            <canvas ref="cvTga" />
          </div>
          <!-- TGA 特征参数 -->
          <table v-if="dlgData.tga_features?.length" class="feat-tbl" style="margin-top:8px">
            <thead><tr><th>参数</th><th>典型值</th><th>说明</th></tr></thead>
            <tbody>
              <tr v-for="f in dlgData.tga_features" :key="f.parameter">
                <td class="feat-param">{{ f.parameter }}</td>
                <td class="feat-val">{{ f.value }}</td>
                <td class="feat-note">{{ f.note }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 特征峰表 -->
      <div class="chart-label" style="margin-top:14px">FTIR 特征峰（{{ dlgData.ftir_peaks?.length }} 条）</div>
      <table class="peak-tbl">
        <thead><tr><th>波数 (cm⁻¹)</th><th>归属</th><th>强度</th></tr></thead>
        <tbody>
          <tr v-for="p in dlgData.ftir_peaks" :key="p.wavenumber">
            <td class="td-wn">{{ p.wavenumber }}</td>
            <td>{{ p.assignment }}</td>
            <td :class="ic(p.intensity)">{{ p.intensity }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 鉴别要点 -->
      <template v-if="dlgData.notes || dlgData.confusions">
        <div v-if="dlgData.notes"      class="info-row"><span class="ik">鉴别要点</span><span class="iv">{{ dlgData.notes }}</span></div>
        <div v-if="dlgData.confusions" class="info-row warn"><span class="ik">常见混淆</span><span class="iv">{{ dlgData.confusions }}</span></div>
      </template>

      <!-- 汽车典型添加剂配方包 -->
      <template v-if="dlgData.automotive_additives">
        <div class="chart-label" style="margin-top:16px">
          汽车典型配混添加剂
          <span class="app-tag">{{ dlgData.automotive_additives.typical_applications }}</span>
        </div>
        <table class="additive-tbl">
          <thead><tr><th>添加剂</th><th>典型用量</th><th>FTIR干扰峰</th><th>注意事项</th></tr></thead>
          <tbody>
            <tr v-for="a in dlgData.automotive_additives.additives" :key="a.name">
              <td class="add-name">{{ a.name }}</td>
              <td class="add-level">{{ a.typical_level }}</td>
              <td class="add-ftir">{{ a.ftir_impact }}</td>
              <td class="add-caution">{{ a.caution || '' }}</td>
            </tr>
          </tbody>
        </table>
      </template>

    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import { apiFetch } from '../apiFetch'

Chart.register(...registerables)

// ── 抽屉 ──────────────────────────────────────────────
const open = defineModel('open', { default: false })

// ── 分类树 ────────────────────────────────────────────
const tree     = ref([])   // [{ super, subs:[{ group, items:[{id,label}] }] }]
const expanded = ref(new Set())

watch(open, async (v) => {
  if (v && tree.value.length === 0) await loadTree()
})

async function loadTree() {
  const r = await apiFetch('/api/v1/knowledge/entries')
  const entries = await r.json()

  const superMap = new Map()
  for (const e of entries) {
    if (!superMap.has(e.super_group)) superMap.set(e.super_group, new Map())
    const subMap = superMap.get(e.super_group)
    if (!subMap.has(e.display_group)) subMap.set(e.display_group, [])
    subMap.get(e.display_group).push({ id: e.id, label: e.label })
  }

  tree.value = [...superMap.entries()].map(([sg, subs]) => ({
    super: sg,
    subs: [...subs.entries()].map(([dg, items]) => ({ group: dg, items })),
  }))
}

function toggle(sg) {
  const s = new Set(expanded.value)
  s.has(sg) ? s.delete(sg) : s.add(sg)
  expanded.value = s
}

// ── 材料弹窗 ──────────────────────────────────────────
const dlgOpen  = ref(false)
const dlgData  = ref(null)
const dlgTitle = ref('')
const cvFtir   = ref(null)
const cvDsc    = ref(null)
const cvTga    = ref(null)
let charts     = []

// ── FTIR 峰悬停 Tooltip ────────────────────────────────────────
const ttVisible = ref(false)
const ttData    = ref({ wavenumber: '', assignment: '', intensity: '' })
const ttStyle   = ref({})
let _ftirHoverCleanup = null

async function openMaterial(id) {
  const r = await apiFetch(`/api/v1/knowledge/entry/${id}`)
  dlgData.value = await r.json()
  const names = dlgData.value.common_names || []
  dlgTitle.value = `${id}  ${names[0] || ''}`
  dlgOpen.value = true
}

// @opened 事件触发后 canvas 已在 DOM 中
function drawCharts() {
  destroyCharts()
  const d = dlgData.value
  if (!d) return
  charts.push(buildFtir(cvFtir.value, d.ftir_peaks || []))
  charts.push(buildDsc(cvDsc.value,   d.dsc_parameters || {}))
  charts.push(buildTga(cvTga.value,   d.tga_characteristics || {}))
  setupFtirHover(cvFtir.value, d.ftir_peaks || [])
}

function destroyCharts() {
  _ftirHoverCleanup?.()
  _ftirHoverCleanup = null
  charts.forEach(c => c?.destroy())
  charts = []
  ttVisible.value = false
}

// ── FTIR 峰位悬停检测 ─────────────────────────────────────────
function setupFtirHover(canvas, peaks) {
  if (!canvas || !peaks.length) return
  const onMove = (e) => {
    const chartInst = charts[0]
    if (!chartInst) return
    const rect = canvas.getBoundingClientRect()
    const mx   = e.clientX - rect.left
    const wn   = chartInst.scales.x.getValueForPixel(mx)
    if (wn == null || wn < 400 || wn > 4000) { ttVisible.value = false; return }

    // 在波数空间内寻找 ±70 cm⁻¹ 以内的最近峰
    let nearest = null, minDist = 70
    for (const p of peaks) {
      const d = Math.abs(p.wavenumber - wn)
      if (d < minDist) { minDist = d; nearest = p }
    }
    if (nearest) {
      ttVisible.value = true
      ttData.value    = nearest
      const x = Math.min(mx + 14, rect.width - 200)
      const y = Math.max(e.clientY - rect.top - 72, 4)
      ttStyle.value = { left: x + 'px', top: y + 'px' }
    } else {
      ttVisible.value = false
    }
  }
  canvas.addEventListener('mousemove', onMove)
  _ftirHoverCleanup = () => canvas.removeEventListener('mousemove', onMove)
}

// ── FTIR 高斯合成 ─────────────────────────────────────
const FTIR_AMP = { '很强': 85, '强': 60, '中': 35, '弱': 18, '很弱': 10 }

function buildFtir(canvas, peaks) {
  if (!canvas) return null
  const xs = []
  for (let v = 4000; v >= 400; v -= 4) xs.push(v)
  const data = xs.map(x => {
    let a = 0
    for (const p of peaks) a += (FTIR_AMP[p.intensity] ?? 40) * Math.exp(-((x - p.wavenumber) ** 2) / (2 * 18 ** 2))
    return { x, y: Math.max(0, 100 - a) }
  })
  return new Chart(canvas, {
    type: 'line',
    data: { datasets: [{ data, borderColor: '#4d9cf5', borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: { target: 'origin', above: 'rgba(77,156,245,0.07)' } }] },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: i => `${i[0].raw.x} cm⁻¹`, label: i => `T = ${i[0].raw.y.toFixed(1)} %` } } },
      scales: {
        x: { type: 'linear', reverse: true, min: 400, max: 4000, title: { display: true, text: '波数 (cm⁻¹)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', stepSize: 500, font: { size: 9 } }, grid: { color: '#1a2240' } },
        y: { min: 0, max: 100, title: { display: true, text: '透过率 (%T)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', font: { size: 9 } }, grid: { color: '#1a2240' } },
      },
    },
  })
}

// ── DSC 合成 ──────────────────────────────────────────
function parseTemps(str) {
  if (!str) return []
  // 先把 "160-175" 里的范围连字符替换为逗号，避免被识别为负号
  // 只替换 "数字-数字" 模式，保留真正的负温度如 "-55"
  const normalized = str.replace(/(\d)-(\d)/g, '$1,$2')
  const m = normalized.match(/-?\d+(?:\.\d+)?/g)
  return m ? m.map(Number) : []
}
function midpoint(str) {
  const nums = parseTemps(str)
  if (!nums.length) return null
  return nums.reduce((a, b) => a + b, 0) / nums.length
}
function isAmorphous(str) {
  return !str || str.includes('无结晶') || str.includes('非晶') || str.includes('amorphous')
}

function buildDsc(canvas, dsc) {
  if (!canvas) return null
  const tg = midpoint(dsc.tg_range)
  const tm = isAmorphous(dsc.tm_range) ? null : midpoint(dsc.tm_range)
  const dh = tm ? Math.min(Math.abs(midpoint(dsc.delta_h_range) ?? 80), 80) : 0

  // 使用材料特定熔融峰半高宽；FWHM → σ = FWHM / 2.355
  const fwhm = dsc.peak_halfwidth_c ?? 10
  const sigmaMelt = fwhm / 2.355

  const xs = []
  for (let t = -150; t <= 500; t += 2) xs.push(t)

  const data = xs.map(t => {
    let hf = 0.5   // 小幅向上漂移基线（热容效应）
    if (tg) hf += 0.4 / (1 + Math.exp(-(t - tg) / 4))
    if (tm) hf -= (dh / 80 * 12) * Math.exp(-((t - tm) ** 2) / (2 * sigmaMelt ** 2))
    return { x: t, y: hf }
  })

  const xMin = Math.min(-80, (tg ?? 0) - 60)
  const xMax = Math.max(300, (tm ?? 200) + 80)

  return new Chart(canvas, {
    type: 'line',
    data: { datasets: [{ data, borderColor: '#f0a040', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: false }] },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { title: i => `${i[0].raw.x.toFixed(0)} °C`, label: i => `热流 ${i[0].raw.y.toFixed(2)} mW/mg` } },
        annotation: {},
      },
      scales: {
        x: { type: 'linear', min: xMin, max: xMax, title: { display: true, text: '温度 (°C)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', font: { size: 9 } }, grid: { color: '#1a2240' } },
        y: { title: { display: true, text: '热流 (mW/mg)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', font: { size: 9 } }, grid: { color: '#1a2240' } },
      },
    },
  })
}

// ── TGA 合成 ──────────────────────────────────────────
function parseResidue(str) {
  if (!str) return 0
  const m = str.match(/\d+(?:\.\d+)?/)
  return m ? parseFloat(m[0]) : 0
}

function buildTga(canvas, tga) {
  if (!canvas) return null

  const xs = []
  for (let t = 25; t <= 700; t += 5) xs.push(t)

  let data

  if (tga.tga_steps?.length) {
    // ── 多步分解（PVC/EVA/TPU/CR/SEBS/ABS）──
    const totalLoss = tga.tga_steps.reduce((s, step) => s + step.mass_loss_pct, 0)
    const residue   = Math.max(0, 100 - totalLoss)
    data = xs.map(t => {
      let w = residue
      for (const step of tga.tga_steps) {
        const sigma    = Math.max((step.midpoint_c - step.onset_c) / 2.3, 5)
        const fraction = 1 / (1 + Math.exp((t - step.midpoint_c) / sigma))
        w += step.mass_loss_pct * fraction
      }
      return { x: t, y: Math.max(residue, Math.min(100, w)) }
    })
  } else {
    // ── 单步：优先使用精确中点温度 ──
    const onset   = tga.tga_onset_c   ?? midpoint(tga.onset_decomposition) ?? 400
    const mp      = tga.tga_midpoint_c ?? (onset + 60)
    const sigma   = Math.max((mp - onset) / 2.3, 8)
    const residue = parseResidue(tga.residue ?? tga.weight_loss_range ?? '0')
    data = xs.map(t => {
      const w = residue + (100 - residue) / (1 + Math.exp((t - mp) / sigma))
      return { x: t, y: Math.max(residue, Math.min(100, w)) }
    })
  }

  return new Chart(canvas, {
    type: 'line',
    data: { datasets: [{ data, borderColor: '#5dcc8a', borderWidth: 1.5, pointRadius: 0, tension: 0.2, fill: { target: 'end', below: 'rgba(93,204,138,0.07)' } }] },
    options: {
      animation: false, responsive: true, maintainAspectRatio: false, parsing: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: i => `${i[0].raw.x} °C`, label: i => `质量 ${i[0].raw.y.toFixed(1)} %` } } },
      scales: {
        x: { type: 'linear', min: 25, max: 700, title: { display: true, text: '温度 (°C)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', stepSize: 100, font: { size: 9 } }, grid: { color: '#1a2240' } },
        y: { min: 0, max: 105, title: { display: true, text: '质量 (%)', color: '#4a5d7a', font: { size: 10 } }, ticks: { color: '#4a5d7a', font: { size: 9 } }, grid: { color: '#1a2240' } },
      },
    },
  })
}

// ── 工具 ─────────────────────────────────────────────
const ic = v => ({ '很强': 'int-vs', '强': 'int-s', '中': 'int-m', '弱': 'int-w', '很弱': 'int-vw' }[v] || '')
</script>

<style>
/* 抽屉 */
.kb-drawer .el-drawer__body   { padding: 0 !important; overflow-y: auto; background: #0b1018; }
.kb-drawer .el-drawer__header { background: #131929; border-bottom: 1px solid #1e2840; padding: 12px 20px; margin-bottom: 0; }
.kb-drawer .el-drawer__title  { color: #c8d3e8 !important; font-size: 14px !important; font-weight: 600 !important; }
.kb-drawer .el-drawer__close-btn { color: #4a5d7a !important; }

/* 弹窗 */
.mat-dlg .el-dialog            { background: #0f1320 !important; border: 1px solid #1e2840; }
.mat-dlg .el-dialog__header    { background: #131929; padding: 14px 20px; border-bottom: 1px solid #1e2840; }
.mat-dlg .el-dialog__title     { color: #c8d3e8 !important; font-size: 15px !important; font-weight: 700 !important; }
.mat-dlg .el-dialog__headerbtn .el-dialog__close { color: #4a5d7a !important; }
.mat-dlg .el-dialog__body      { padding: 18px 22px; }
</style>

<style scoped>
/* ── 菜单 ── */
.kb-menu { padding: 8px 0 24px; }

.cat-block { border-bottom: 1px solid #111825; }

.cat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 18px;
  cursor: pointer;
  user-select: none;
  transition: background 0.12s;
}
.cat-head:hover { background: #111d30; }

.cat-name  { font-size: 14px; font-weight: 600; color: #a0b4cc; }
.cat-arrow {
  font-size: 10px;
  color: #3a4d6e;
  transition: transform 0.2s;
}
.cat-arrow.open { transform: rotate(90deg); color: #4d9cf5; }

.cat-body { padding-bottom: 6px; }

.sub-block { margin-top: 2px; }

.sub-name {
  padding: 5px 18px 3px 28px;
  font-size: 10px;
  font-weight: 700;
  color: #2a4060;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mat-link {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 7px 18px 7px 32px;
  cursor: pointer;
  transition: background 0.1s;
  border-left: 2px solid transparent;
}
.mat-link:hover {
  background: #112040;
  border-left-color: #4d9cf5;
}
.mat-link-id {
  font-size: 12px;
  font-weight: 600;
  color: #4d9cf5;
  flex-shrink: 0;
  min-width: 48px;
}
.mat-link-label {
  font-size: 11px;
  color: #5a6d8a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 弹窗内容 ── */
.dlg-body { display: flex; flex-direction: column; gap: 12px; }

.dlg-tags  { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.dlg-aliases { font-size: 12px; color: #3a4d6e; margin-left: 4px; }

.chart-label {
  font-size: 11px;
  font-weight: 600;
  color: #4a5d7a;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}
.chart-box {
  background: #0d1220;
  border: 1px solid #1a2440;
  border-radius: 6px;
  padding: 8px 12px;
}
.chart-wide { height: 200px; }
.ftir-wrap  { position: relative; overflow: visible; }

/* FTIR 峰悬停 Tooltip */
.ftir-tt {
  position: absolute;
  z-index: 20;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  gap: 3px;
  background: #0b1628;
  border: 1px solid #2a4878;
  border-radius: 7px;
  padding: 8px 12px;
  min-width: 170px;
  max-width: 230px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, .6);
}
.tt-wn {
  font-size: 13px;
  font-weight: 700;
  color: #c8d3e8;
  font-variant-numeric: tabular-nums;
}
.tt-asgn {
  font-size: 11px;
  color: #7eb8e0;
  line-height: 1.4;
}
.tt-int {
  font-size: 10px;
}
.row2 { display: flex; gap: 14px; }
.half { flex: 1; min-width: 0; }
.half .chart-box { height: 160px; }

/* 峰表 */
.peak-tbl { width: 100%; border-collapse: collapse; font-size: 12px; }
.peak-tbl th { background: #0d1525; color: '#4a5d7a'; padding: 5px 8px; text-align: left; border-bottom: 1px solid #1a2440; font-weight: 500; color: #4a5d7a; }
.peak-tbl td { padding: 4px 8px; border-bottom: 1px solid #0f1828; color: #7a8fa8; }
.peak-tbl tr:hover td { background: #0f1a2c; }
.td-wn { color: #c8d3e8; font-weight: 600; font-variant-numeric: tabular-nums; }

/* DSC / TGA 特征参数表 */
.feat-tbl { width: 100%; border-collapse: collapse; font-size: 11px; }
.feat-tbl th { background: #0d1525; color: #4a5d7a; padding: 4px 6px; text-align: left; border-bottom: 1px solid #1a2440; font-weight: 500; }
.feat-tbl td { padding: 3px 6px; border-bottom: 1px solid #0f1828; vertical-align: top; }
.feat-tbl tr:hover td { background: #0f1a2c; }
.feat-param { color: #8ab4d8; font-weight: 600; white-space: nowrap; width: 38%; }
.feat-val   { color: #c8d3e8; font-weight: 600; white-space: nowrap; width: 22%; font-variant-numeric: tabular-nums; }
.feat-note  { color: #5a6d8a; line-height: 1.4; width: 40%; }
.int-vs { color: #e56; font-weight: 700; }
.int-s  { color: #f90; }
.int-m  { color: #4d9cf5; }
.int-w  { color: #4a5d7a; }
.int-vw { color: #2a3550; }

/* 附加信息 */
.info-row { display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px solid #0f1828; font-size: 12px; line-height: 1.6; }
.info-row.warn .ik { color: #c87020; }
.ik { width: 68px; flex-shrink: 0; color: #4d9cf5; font-weight: 600; }
.iv { color: #5a6d8a; }

/* 汽车添加剂表 */
.app-tag { font-size: 10px; color: #3a7040; background: #0a1a0f; border: 1px solid #1a3020; border-radius: 4px; padding: 1px 6px; margin-left: 8px; font-weight: 400; letter-spacing: 0; }
.additive-tbl { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 4px; }
.additive-tbl th { background: #0d1525; color: #4a5d7a; padding: 4px 6px; text-align: left; border-bottom: 1px solid #1a2440; font-weight: 500; }
.additive-tbl td { padding: 4px 6px; border-bottom: 1px solid #0f1828; vertical-align: top; line-height: 1.5; }
.additive-tbl tr:hover td { background: #0f1a2c; }
.add-name  { color: #7eb8e0; font-weight: 600; width: 26%; }
.add-level { color: #5dcc8a; white-space: nowrap; width: 14%; font-variant-numeric: tabular-nums; }
.add-ftir  { color: #8a9bb5; width: 40%; }
.add-caution { color: #c87020; font-style: italic; width: 20%; }
</style>
