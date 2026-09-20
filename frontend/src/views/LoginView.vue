<template>
  <main class="login-page">
    <section class="login-card">
      <template v-if="previewMode">
        <div class="logo">⬡</div>
        <h1>线上发布预览</h1>
        <p>该 GitHub Pages 页面已发布，但在线 API 服务器尚未配置。登录、上传、AI 分析和共享数据将在后端 HTTPS 服务部署后启用。</p>
        <el-alert title="这是静态预览，不会发送文件或调用 AI。" type="warning" :closable="false" class="error" />
        <el-button type="primary" size="large" class="submit" @click="enterPreview">浏览发布预览</el-button>
      </template>
      <template v-else>
        <div class="logo">⬡</div>
        <h1>谱图智能分析系统</h1>
        <p>请登录后继续使用</p>
        <el-form @submit.prevent="submit">
          <el-form-item>
            <el-input v-model="username" autocomplete="username" placeholder="用户名" size="large" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="password" type="password" show-password autocomplete="current-password" placeholder="密码" size="large" @keyup.enter="submit" />
          </el-form-item>
          <el-alert v-if="error" :title="error" type="error" :closable="false" class="error" />
          <el-button type="primary" size="large" native-type="submit" :loading="loading" class="submit">登录</el-button>
        </el-form>
      </template>
    </section>
  </main>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { apiUrl, hasRemoteApi } from '../api'
import { auth } from '../auth'

const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const previewMode = import.meta.env.MODE === 'github-pages' && !hasRemoteApi

function enterPreview() {
  auth.user = { username: '发布预览', is_admin: false, preview: true }
  auth.loaded = true
  router.replace('/')
}

async function submit() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(apiUrl('/api/v1/auth/login'), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '登录失败')
    auth.user = data
    auth.loaded = true
    router.replace(typeof route.query.redirect === 'string' ? route.query.redirect : '/')
  } catch (e) {
    error.value = e.message || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; background: radial-gradient(circle at 50% 0%, #1d3052 0, #0f1320 48%); padding: 24px; }
.login-card { width: min(100%, 390px); padding: 38px; background: rgba(19, 25, 41, .97); border: 1px solid #2a3b5d; border-radius: 16px; box-shadow: 0 24px 80px rgba(0,0,0,.35); text-align: center; }
.logo { color: #62aaf9; font-size: 44px; margin-bottom: 10px; }
h1 { margin: 0; color: #dbeaff; font-size: 21px; }
p { margin: 10px 0 28px; color: #7287a7; font-size: 13px; }
.error { margin-bottom: 16px; text-align: left; }
.submit { width: 100%; margin-top: 8px; }
</style>
