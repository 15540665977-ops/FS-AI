<template>
  <div class="page">
    <div class="page-title">一致性检验</div>
    <el-alert type="info" :closable="false" show-icon>
      上传来料批次谱图，与标准谱图库基准版本对比，生成结构化差异报告
    </el-alert>
    <div class="coming">
      <el-icon class="coming-icon"><DocumentChecked /></el-icon>
      <p>功能开发中……</p>
      <p class="sub">请先使用「失效分析」主页上传谱图，选择「一致性检验」分析类型</p>
    </div>
  </div>
</template>

<script setup>
import { DocumentChecked } from '@element-plus/icons-vue'
</script>

<style scoped>
.page { padding: 32px; }
.page-title { font-size: 20px; font-weight: 600; color: #d0dff5; margin-bottom: 20px; }
.coming {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px;
  color: #6a7d9a;
}
.coming-icon { font-size: 56px; color: #2a3550; margin-bottom: 16px; }
.coming p { font-size: 15px; }
.coming .sub { font-size: 13px; margin-top: 6px; color: #4a5d7a; }
</style>
