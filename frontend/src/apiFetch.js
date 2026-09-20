import { apiUrl } from './api'

export async function apiFetch(path, options = {}) {
  return fetch(apiUrl(path), {
    credentials: 'include',
    ...options,
  })
}
