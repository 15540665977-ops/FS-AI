import { reactive } from 'vue'
import { apiUrl, hasRemoteApi } from './api'

export const auth = reactive({
  user: null,
  loaded: false,
})

export async function loadCurrentUser() {
  if (import.meta.env.MODE === 'github-pages' && !hasRemoteApi) {
    auth.user = { username: '发布预览', is_admin: false, preview: true }
    auth.loaded = true
    return auth.user
  }
  const response = await fetch(apiUrl('/api/v1/auth/me'), { credentials: 'include' })
  if (!response.ok) {
    auth.user = null
    auth.loaded = true
    return null
  }
  auth.user = await response.json()
  auth.loaded = true
  return auth.user
}

export async function logout() {
  if (auth.user?.preview) {
    auth.user = null
    auth.loaded = true
    return
  }
  await fetch(apiUrl('/api/v1/auth/logout'), { method: 'POST', credentials: 'include' })
  auth.user = null
  auth.loaded = true
}
