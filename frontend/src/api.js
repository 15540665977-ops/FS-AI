const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, '') || ''

export const apiBaseUrl = rawApiBaseUrl
export const hasRemoteApi = Boolean(rawApiBaseUrl)

export function apiUrl(path) {
  if (!path.startsWith('/')) throw new Error(`API path must start with '/': ${path}`)
  return `${apiBaseUrl}${path}`
}

export function uploadUrl(path) {
  if (!path.startsWith('/')) throw new Error(`Upload path must start with '/': ${path}`)
  return `${apiBaseUrl}/uploads${path}`
}
