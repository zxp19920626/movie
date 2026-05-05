export interface PermissionAction {
  code: string
  label: string
}

export interface PermissionModule {
  module: string
  label: string
  actions: PermissionAction[]
}

export interface PermissionTree {
  tree: PermissionModule[]
  all_codes: string[]
  seed_roles: string[]
}

export interface AdminRole {
  id: number
  code: string
  name: string
  is_super_admin: boolean
  is_builtin: boolean
  permissions: string[]
  created_at: string
}

export interface AdminUserRow {
  id: number
  email: string
  display_name: string
  role_id: number
  role_code: string
  role_name: string
  is_super_admin: boolean
  app_scope: string[]
  status: 'active' | 'suspended'
  last_login_at: string | null
  created_at: string
}

export interface RoleListResp {
  items: AdminRole[]
  total: number
}

export interface AdminListResp {
  items: AdminUserRow[]
  total: number
}

export interface RoleCreatePayload {
  code: string
  name: string
  permissions: string[]
}

export interface RoleUpdatePayload {
  name?: string
  permissions?: string[]
}

export interface AdminCreatePayload {
  email: string
  password: string
  display_name?: string
  role_id: number
  app_scope?: string[]
}

export interface AdminUpdatePayload {
  display_name?: string
  role_id?: number
  app_scope?: string[]
  status?: 'active' | 'suspended'
  password?: string
}
