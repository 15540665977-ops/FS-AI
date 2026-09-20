<template>
  <div class="page">
    <div class="page-header">
      <div class="page-title">标准谱图库</div>
      <el-button type="primary" :icon="Plus" @click="showDialog = true">录入新谱图</el-button>
    </div>

    <!-- 检索栏 -->
    <div class="search-bar">
      <el-input v-model="search" placeholder="按材料名 / 牌号 / 供应商搜索…" :prefix-icon="Search" clearable style="width: 320px" @input="loadLibrary" />
    </div>

    <!-- 谱图卡片列表 -->
    <div class="card-grid" v-if="items.length">
      <div v-for="item in items" :key="item.id" class="spec-card">
        <div class="card-main">
          <div class="mat-name">{{ item.material_name }}</div>
          <div class="mat-meta">
            <span>{{ item.grade || '—' }}</span>
            <span class="sep">·</span>
            <span>{{ item.supplier || '—' }}</span>
          </div>
          <div class="mat-date">批准日期：{{ item.approved_date || '—' }}</div>
        </div>
        <div class="card-images">
          <img v-if="item.ir_image_path" :src="'/uploads/' + item.ir_image_path" alt="IR" class="spec-thumb" />
          <img v-if="item.dsc_image_path" :src="'/uploads/' + item.dsc_image_path" alt="DSC" class="spec-thumb" />
          <img v-if="item.tga_image_path" :src="'/uploads/' + item.tga_image_path" alt="TGA" class="spec-thumb" />
        </div>
      </div>
    </div>
    <div v-else class="empty-hint">暂无标准谱图，点击右上角「录入新谱图」添加</div>

    <!-- 录入对话框 -->
    <el-dialog v-model="showDialog" title="录入标准谱图" width="500px">
      <el-form :model="form" label-width="90px" size="default">
        <el-form-item label="材料名称" required>
          <el-input v-model="form.material_name" placeholder="如：PP-T20" />
        </el-form-item>
        <el-form-item label="牌号">
          <el-input v-model="form.grade" placeholder="如：HJ730" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="form.supplier" />
        </el-form-item>
        <el-form-item label="批准日期">
          <el-date-picker v-model="form.approved_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="FTIR 谱图">
          <el-upload action="" :auto-upload="false" :on-change="f => form.ir_file = f.raw" accept=".png,.jpg,.jpeg">
            <el-button size="small">选择图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="DSC 谱图">
          <el-upload action="" :auto-upload="false" :on-change="f => form.dsc_file = f.raw" accept=".png,.jpg,.jpeg">
            <el-button size="small">选择图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="TGA 谱图">
          <el-upload action="" :auto-upload="false" :on-change="f => form.tga_file = f.raw" accept=".png,.jpg,.jpeg">
            <el-button size="small">选择图片</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSpectrum">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { apiFetch } from '../apiFetch'

const items = ref([])
const search = ref('')
const showDialog = ref(false)
const saving = ref(false)
const form = ref({ material_name: '', grade: '', supplier: '', approved_date: '', notes: '', ir_file: null, dsc_file: null, tga_file: null })

async function loadLibrary() {
  try {
    const url = search.value ? `/api/v1/library/?q=${encodeURIComponent(search.value)}` : '/api/v1/library/'
    const res = await apiFetch(url)
    const data = await res.json()
    items.value = data.items || []
  } catch { /* noop */ }
}

async function saveSpectrum() {
  if (!form.value.material_name) return ElMessage.warning('请填写材料名称')
  saving.value = true
  try {
    const fd = new FormData()
    Object.entries(form.value).forEach(([k, v]) => {
      if (v != null && !k.endsWith('_file')) fd.append(k, v)
    })
    if (form.value.ir_file) fd.append('ir_file', form.value.ir_file)
    if (form.value.dsc_file) fd.append('dsc_file', form.value.dsc_file)
    if (form.value.tga_file) fd.append('tga_file', form.value.tga_file)
    const res = await apiFetch('/api/v1/library/', { method: 'POST', body: fd })
    if (!res.ok) throw new Error(await res.text())
    ElMessage.success('录入成功')
    showDialog.value = false
    loadLibrary()
  } catch (e) {
    ElMessage.error(`保存失败：${e.message}`)
  } finally {
    saving.value = false
  }
}

onMounted(loadLibrary)
</script>

<style scoped>
.page { padding: 28px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; color: #d0dff5; }
.search-bar { margin-bottom: 20px; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.spec-card { background: #1a2240; border: 1px solid #2a3550; border-radius: 10px; padding: 16px; }
.mat-name { font-size: 15px; font-weight: 600; color: #d0dff5; }
.mat-meta { font-size: 12px; color: #6a7d9a; margin-top: 4px; }
.sep { margin: 0 6px; }
.mat-date { font-size: 11px; color: #4a5d7a; margin-top: 4px; }
.card-images { display: flex; gap: 8px; margin-top: 12px; }
.spec-thumb { width: 72px; height: 54px; object-fit: cover; border-radius: 4px; border: 1px solid #2a3550; }
.empty-hint { text-align: center; color: #4a5d7a; padding: 60px; font-size: 14px; }
</style>
