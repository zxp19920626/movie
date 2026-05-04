// movie admin 统一 API 客户端
// dev 走 vite proxy /api → http://localhost:8000
// prod 走同源 /api（FastAPI 由 nginx 反代）
//
// 与 nextstream/admin/src/api/client.ts 的差异：
//   - BASE 改为 /api/v1（FastAPI 版本化命名空间）
//   - localStorage key 改为 mv_admin_token / mv_admin_user
//   - 401 自动 logout 并跳登录
//   - 标准化错误码字段：FastAPI 用 detail，nextstream 用 error
import { useAuthStore } from '@/shared/stores/auth'

const BASE = '/api/v1'

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
}

async function request<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const auth = useAuthStore()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  }
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`

  const res = await fetch(BASE + path, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })

  if (res.status === 204) return null as T
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    if (res.status === 401) auth.logout()
    const err = data as { detail?: string; error?: string; code?: string }
    const msg = err.detail || err.error || `HTTP ${res.status}`
    throw new Error(msg)
  }
  return data as T
}

export const api = {
  get: <T = unknown>(p: string) => request<T>(p),
  post: <T = unknown>(p: string, body?: unknown) => request<T>(p, { method: 'POST', body }),
  patch: <T = unknown>(p: string, body?: unknown) => request<T>(p, { method: 'PATCH', body }),
  put: <T = unknown>(p: string, body?: unknown) => request<T>(p, { method: 'PUT', body }),
  del: <T = unknown>(p: string) => request<T>(p, { method: 'DELETE' }),
}
