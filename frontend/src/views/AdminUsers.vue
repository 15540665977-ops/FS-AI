<template>
  <main class="users-page">
    <header class="header">
      <div>
        <router-link to="/" class="back">← 返回分析</router-link>
        <h1>用户管理</h1>
        <p>创建、重置和停用系统账户。</p>
      </div>
      <el-button type="primary" @click="dialogOpen = true">创建用户</el-button>
    </header>

    <el-alert title="管理员可查看和管理全部账户；密码只以安全哈希形式保存。" type="info" :closable="false" class="notice" />
    <el-table :data="users" v-loading="loading" class="table">
      <el-table-column prop="username" label="用户名" />
      <el-table-column label="角色" width="110">
        <template #default="{ row }"><el-tag :type="row.is_admin ? 'warning' : 'info'">{{ row.is_admin ? '管理员' : '普通用户' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'danger'">{{ row.is_active ? '启用' : '已停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="创建时间" width="180"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
      <el-table-column label="操作" width="250">
        <template #default="{ row }">
          <el-button text type="primary" @click="openReset(row)">重置密码</el-button>
          <el-button text :type="row.is_active ? 'danger' : 'success'" @click="toggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogOpen" title="创建用户" width="420px" destroy-on-close>
      <el-form label-position="top" @submit.prevent="createUser">
        <el-form-item label="用户名"><el-input v-model="newUser.username" autocomplete="off" placeholder="3–64 位：字母、数字、._-" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="newUser.password" type="password" show-password autocomplete="new-password" placeholder="至少 10 个字符" /></el-form-item>
        <el-checkbox v-model="newUser.is_admin">授予管理员权限</el-checkbox>
      </el-form>
      <template #footer><el-button @click="dialogOpen = false">取消</el-button><el-button type="primary" :loading="saving" @click="createUser">创建</el-button></template>
    </el-dialog>

    <el-dialog v-model="resetOpen" title="重置密码" width="420px" destroy-on-close>
      <p class="reset-copy">正在为 <strong>{{ selected?.username }}</strong> 设置新密码。</p>
      <el-input v-model="resetPassword" type="password" show-password autocomplete="new-password" placeholder="至少 10 个字符" @keyup.enter="resetUserPassword" />
      <template #footer><el-button @click="resetOpen = false">取消</el-button><el-button type="primary" :loading="saving" @click="resetUserPassword">保存新密码</el-button></template>
    </el-dialog>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiFetch } from '../apiFetch'

const users = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogOpen = ref(false)
const resetOpen = ref(false)
const selected = ref(null)
const resetPassword = ref('')
const newUser = ref({ username: '', password: '', is_admin: false })
const formatDate = (value) => value ? new Date(value).toLocaleString('zh-CN') : '—'

async function request(url, options = {}) {
  const response = await apiFetch(url, options)
  const payload = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new Error(payload?.detail || '请求失败')
  return payload
}

async function loadUsers() {
  loading.value = true
  try { users.value = await request('/api/v1/auth/users') }
  catch (error) { ElMessage.error(error.message) }
  finally { loading.value = false }
}

async function createUser() {
  saving.value = true
  try {
    await request('/api/v1/auth/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newUser.value) })
    ElMessage.success('用户已创建')
    dialogOpen.value = false
    newUser.value = { username: '', password: '', is_admin: false }
    await loadUsers()
  } catch (error) { ElMessage.error(error.message) }
  finally { saving.value = false }
}

function openReset(user) {
  selected.value = user
  resetPassword.value = ''
  resetOpen.value = true
}

async function resetUserPassword() {
  if (!selected.value) return
  saving.value = true
  try {
    await request(`/api/v1/auth/users/${selected.value.id}/password`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: resetPassword.value }) })
    ElMessage.success('密码已重置')
    resetOpen.value = false
  } catch (error) { ElMessage.error(error.message) }
  finally { saving.value = false }
}

async function toggleActive(user) {
  const nextState = !user.is_active
  try {
    await ElMessageBox.confirm(`确定${nextState ? '启用' : '停用'}用户「${user.username}」吗？`, '确认操作', { type: 'warning' })
    await request(`/api/v1/auth/users/${user.id}/active?is_active=${nextState}`, { method: 'PUT' })
    ElMessage.success(nextState ? '用户已启用' : '用户已停用')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error.message || '操作失败')
  }
}

onMounted(loadUsers)
</script>

<style scoped>
.users-page { min-height: 100vh; padding: 32px max(24px, calc(50vw - 560px)); background: #0f1320; color: #c8d3e8; }
.header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 24px; }
.back { display: inline-block; margin-bottom: 12px; color: #62aaf9; font-size: 13px; text-decoration: none; }
h1 { margin: 0; color: #e1edff; font-size: 23px; } p { margin: 7px 0 0; color: #7083a1; font-size: 13px; }
.notice { margin-bottom: 18px; }.table { border-radius: 9px; overflow: hidden; }.reset-copy { margin: 0 0 14px; color: #8497b5; }
</style>
