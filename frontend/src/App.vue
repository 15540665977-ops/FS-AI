<template>
  <el-container class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <span class="logo-icon">⬡</span>
        <span class="logo-text">谱图分析系统</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#1a1f2e"
        text-color="#8a9bb5"
        active-text-color="#4d9cf5"
      >
        <el-menu-item index="/failure-analysis">
          <el-icon><Search /></el-icon>
          <span>失效分析</span>
        </el-menu-item>
        <el-menu-item index="/consistency-check">
          <el-icon><DocumentChecked /></el-icon>
          <span>一致性检验</span>
        </el-menu-item>
        <el-menu-item index="/standard-library">
          <el-icon><Files /></el-icon>
          <span>标准谱图库</span>
        </el-menu-item>
        <el-menu-item index="/case-records">
          <el-icon><Folder /></el-icon>
          <span>案例记录</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { Search, DocumentChecked, Files, Folder } from '@element-plus/icons-vue'
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0f1320;
  color: #c8d3e8;
}

.app-container {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  background: #1a1f2e;
  border-right: 1px solid #2a3550;
  display: flex;
  flex-direction: column;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 16px;
  border-bottom: 1px solid #2a3550;
}

.logo-icon {
  font-size: 22px;
  color: #4d9cf5;
}

.logo-text {
  font-size: 14px;
  font-weight: 600;
  color: #e2e8f4;
  letter-spacing: 0.5px;
}

.el-menu { border-right: none !important; margin-top: 8px; }

.el-menu-item {
  border-radius: 6px;
  margin: 2px 8px;
  height: 42px;
  line-height: 42px;
}

.el-menu-item.is-active {
  background: rgba(77, 156, 245, 0.12) !important;
}

.main-content {
  background: #0f1320;
  overflow-y: auto;
  padding: 0;
}
</style>
