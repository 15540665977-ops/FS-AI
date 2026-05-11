<template>
  <div class="upload-zone"
    :class="{ 'drag-over': isDragging, 'has-files': files.length > 0 }"
    @dragover.prevent="isDragging = true"
    @dragleave="isDragging = false"
    @drop.prevent="onDrop"
    @click="triggerInput"
  >
    <input
      ref="inputRef"
      type="file"
      multiple
      :accept="accept"
      style="display: none"
      @change="onFileChange"
    />

    <!-- 空状态 -->
    <template v-if="files.length === 0">
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <p class="upload-hint-main">拖拽谱图文件到此处，或点击上传</p>
      <p class="upload-hint-sub">支持 PNG / JPG / PDF，可同时上传多张谱图</p>
    </template>

    <!-- 已选文件预览 -->
    <template v-else>
      <div class="preview-grid" @click.stop>
        <div
          v-for="(f, i) in files"
          :key="i"
          class="preview-item"
        >
          <img v-if="f.preview" :src="f.preview" class="preview-img" />
          <div v-else class="preview-pdf">
            <el-icon><Document /></el-icon>
            <span>{{ f.name }}</span>
          </div>
          <div class="preview-label">{{ f.name }}</div>
          <el-button
            class="remove-btn"
            type="danger"
            circle
            size="small"
            :icon="Close"
            @click.stop="removeFile(i)"
          />
        </div>

        <!-- 追加更多 -->
        <div class="preview-add" @click="triggerInput">
          <el-icon><Plus /></el-icon>
          <span>添加</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled, Document, Close, Plus } from '@element-plus/icons-vue'

const props = defineProps({
  accept: { type: String, default: '.png,.jpg,.jpeg,.pdf' },
  modelValue: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const inputRef = ref(null)
const isDragging = ref(false)
const files = ref([])

function triggerInput() {
  inputRef.value?.click()
}

function buildFileEntry(rawFile) {
  const isPdf = rawFile.name.toLowerCase().endsWith('.pdf')
  return {
    raw: rawFile,
    name: rawFile.name,
    preview: isPdf ? null : URL.createObjectURL(rawFile),
  }
}

function addFiles(rawFiles) {
  const newEntries = Array.from(rawFiles).map(buildFileEntry)
  files.value = [...files.value, ...newEntries]
  emit('update:modelValue', files.value.map(f => f.raw))
}

function onFileChange(e) {
  addFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  addFiles(e.dataTransfer.files)
}

function removeFile(index) {
  const f = files.value[index]
  if (f.preview) URL.revokeObjectURL(f.preview)
  files.value.splice(index, 1)
  emit('update:modelValue', files.value.map(f => f.raw))
}

function clear() {
  files.value.forEach(f => { if (f.preview) URL.revokeObjectURL(f.preview) })
  files.value = []
  emit('update:modelValue', [])
}

defineExpose({ clear })
</script>

<style scoped>
.upload-zone {
  border: 2px dashed #2a3550;
  border-radius: 10px;
  padding: 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  background: #151b2e;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-zone:hover, .upload-zone.drag-over {
  border-color: #4d9cf5;
  background: rgba(77, 156, 245, 0.05);
}

.upload-zone.has-files {
  cursor: default;
  padding: 20px;
  align-items: flex-start;
  justify-content: flex-start;
}

.upload-icon {
  font-size: 40px;
  color: #3a4d6e;
  margin-bottom: 12px;
}

.upload-hint-main {
  font-size: 14px;
  color: #8a9bb5;
  margin-bottom: 4px;
}

.upload-hint-sub {
  font-size: 12px;
  color: #4a5d7a;
}

.preview-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
}

.preview-item {
  position: relative;
  width: 120px;
}

.preview-img {
  width: 120px;
  height: 90px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #2a3550;
  display: block;
}

.preview-pdf {
  width: 120px;
  height: 90px;
  border-radius: 6px;
  border: 1px solid #2a3550;
  background: #1e2840;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #8a9bb5;
  font-size: 12px;
}

.preview-pdf .el-icon { font-size: 28px; color: #4d9cf5; }

.preview-label {
  font-size: 11px;
  color: #5a6d8a;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 120px;
}

.remove-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px !important;
  height: 20px !important;
}

.preview-add {
  width: 120px;
  height: 90px;
  border-radius: 6px;
  border: 2px dashed #2a3550;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #4a5d7a;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}

.preview-add:hover {
  border-color: #4d9cf5;
  color: #4d9cf5;
}

.preview-add .el-icon { font-size: 20px; }
</style>
