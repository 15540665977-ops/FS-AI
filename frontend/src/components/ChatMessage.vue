<template>
  <div class="message" :class="message.role">
    <!-- AI 消息 -->
    <template v-if="message.role === 'assistant'">
      <div class="avatar ai-avatar">AI</div>
      <div class="bubble ai-bubble">
        <div class="content" v-html="renderedContent"></div>
        <div v-if="message.caseNo" class="case-tag">
          <el-icon><DocumentChecked /></el-icon>
          已保存案例 {{ message.caseNo }}
        </div>
        <div v-if="message.streaming" class="cursor-blink">▍</div>
      </div>
    </template>

    <!-- 用户消息 -->
    <template v-else>
      <div class="bubble user-bubble">
        <!-- 上传的图片缩略图 -->
        <div v-if="message.previews && message.previews.length" class="user-images">
          <img
            v-for="(src, i) in message.previews"
            :key="i"
            :src="src"
            class="thumb"
            @click="$emit('preview-image', src)"
          />
        </div>
        <div v-if="message.text" class="content">{{ message.text }}</div>
        <div v-if="message.meta" class="user-meta">
          <el-tag v-if="message.meta.analysisType" size="small" type="info">{{ analysisTypeLabel(message.meta.analysisType) }}</el-tag>
          <el-tag v-if="message.meta.materialHint" size="small">{{ message.meta.materialHint }}</el-tag>
        </div>
      </div>
      <div class="avatar user-avatar">我</div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { DocumentChecked } from '@element-plus/icons-vue'

const props = defineProps({
  message: { type: Object, required: true },
})
defineEmits(['preview-image'])

const TYPE_LABELS = { general: '通用分析', failure: '失效分析', consistency: '一致性检验' }
function analysisTypeLabel(t) { return TYPE_LABELS[t] || t }

// 简单的结构化渲染：把【标题】转为加粗，把 --- 转分割线，保留换行
const renderedContent = computed(() => {
  if (!props.message.content) return ''
  return props.message.content
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/【(.+?)】/g, '<strong class="section-title">【$1】</strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/---+/g, '<hr class="divider" />')
    .replace(/\n/g, '<br />')
})
</script>

<style scoped>
.message {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 24px;
}

.message.user { flex-direction: row-reverse; }

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.ai-avatar {
  background: linear-gradient(135deg, #4d9cf5, #6e54e8);
  color: #fff;
}

.user-avatar {
  background: #2a3550;
  color: #8a9bb5;
}

.bubble {
  max-width: 72%;
  padding: 14px 18px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
}

.ai-bubble {
  background: #1a2240;
  border: 1px solid #2a3550;
  color: #c8d3e8;
}

.user-bubble {
  background: #1e3a5f;
  border: 1px solid #2a4d7a;
  color: #d0dff5;
}

.content { white-space: pre-wrap; word-break: break-word; }

:deep(.section-title) {
  color: #4d9cf5;
  display: block;
  margin-top: 10px;
  margin-bottom: 4px;
  font-size: 13px;
}

:deep(.divider) {
  border: none;
  border-top: 1px solid #2a3550;
  margin: 10px 0;
}

.case-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 10px;
  font-size: 12px;
  color: #4d9cf5;
  padding-top: 8px;
  border-top: 1px solid #2a3550;
}

.cursor-blink {
  display: inline-block;
  color: #4d9cf5;
  animation: blink 0.7s steps(1) infinite;
}

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

.user-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid #2a4d7a;
  cursor: zoom-in;
}

.user-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}
</style>
