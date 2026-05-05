import { api } from '@/shared/api/client'
import type {
  AdminCreatePayload,
  AdminListResp,
  AdminRole,
  AdminUpdatePayload,
  AdminUserRow,
  PermissionTree,
  RoleCreatePayload,
  RoleListResp,
  RoleUpdatePayload,
} from '../types'

const PREFIX = '/admin/rbac'

export const rbacApi = {
  permissionTree: () => api.get<PermissionTree>(`${PREFIX}/permissions/tree`),
  // roles
  listRoles: () => api.get<RoleListResp>(`${PREFIX}/roles?limit=200`),
  createRole: (p: RoleCreatePayload) => api.post<AdminRole>(`${PREFIX}/roles`, p),
  updateRole: (id: number, p: RoleUpdatePayload) =>
    api.patch<AdminRole>(`${PREFIX}/roles/${id}`, p),
  deleteRole: (id: number) => api.del<void>(`${PREFIX}/roles/${id}`),
  // admins
  listAdmins: () => api.get<AdminListResp>(`${PREFIX}/admins?limit=200`),
  createAdmin: (p: AdminCreatePayload) => api.post<AdminUserRow>(`${PREFIX}/admins`, p),
  updateAdmin: (id: number, p: AdminUpdatePayload) =>
    api.patch<AdminUserRow>(`${PREFIX}/admins/${id}`, p),
  disableAdmin: (id: number) => api.del<void>(`${PREFIX}/admins/${id}`),
}
