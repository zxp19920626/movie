// movie admin 鉴权 store
//
// 与 nextstream/admin/src/stores/auth.ts 的差异：
//   - 接口路径：/api/v1/admin/auth/login（多了 /admin/ 前缀，IP 白名单后端中间件兜底）
//   - 返回字段：FastAPI 返 {access_token, refresh_token, user}，不是 {token, user}
//   - localStorage key：mv_admin_token / mv_admin_refresh / mv_admin_user
//   - User 类型：对应 a_admin_users 表（含 app_scope 字段，用于多租户权限隔离）
//   - 多租户：current_app_id 用于切换当前正在查看的 cp_apps 租户
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface AdminUser {
  id: string
  email: string
  display_name: string
  role: string                  // 'super_admin' / 'content_manager' / 'global_ops' / 'service_auditor' / 自定义
  app_scope: string[]           // tenant_uuid 数组；空数组 = 仅 super_admin 才有
  permissions: string[]         // 扁平化权限字符串：'cp.view', 'cp.edit', 'content.view', ...
  is_super_admin: boolean
}

const TOKEN_KEY = 'mv_admin_token'
const REFRESH_KEY = 'mv_admin_refresh'
const USER_KEY = 'mv_admin_user'
const APP_KEY = 'mv_admin_current_app_id'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const refreshToken = ref(localStorage.getItem(REFRESH_KEY) || '')
  const user = ref<AdminUser | null>(JSON.parse(localStorage.getItem(USER_KEY) || 'null'))
  const currentAppId = ref(localStorage.getItem(APP_KEY) || '')

  const isAuthed = computed(() => !!token.value)
  const isSuperAdmin = computed(() => !!user.value?.is_super_admin)

  function hasPermission(perm: string): boolean {
    if (!user.value) return false
    if (user.value.is_super_admin) return true
    return user.value.permissions.includes(perm)
  }

  function canSeeApp(appId: string): boolean {
    if (!user.value) return false
    if (user.value.is_super_admin) return true
    return user.value.app_scope.includes(appId)
  }

  async function login(email: string, password: string) {
    const res = await fetch('/api/v1/admin/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    const data = await res.json()
    if (!res.ok) {
      const msg = (data as { detail?: string }).detail || `登录失败 (${res.status})`
      throw new Error(msg)
    }
    token.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
    localStorage.setItem(TOKEN_KEY, data.access_token)
    localStorage.setItem(REFRESH_KEY, data.refresh_token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    if (data.user.app_scope?.[0] && !currentAppId.value) {
      setCurrentApp(data.user.app_scope[0])
    }
  }

  function setCurrentApp(appId: string) {
    currentAppId.value = appId
    localStorage.setItem(APP_KEY, appId)
  }

  function logout() {
    token.value = ''
    refreshToken.value = ''
    user.value = null
    currentAppId.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(APP_KEY)
  }

  return {
    token,
    refreshToken,
    user,
    currentAppId,
    isAuthed,
    isSuperAdmin,
    hasPermission,
    canSeeApp,
    login,
    setCurrentApp,
    logout,
  }
})
