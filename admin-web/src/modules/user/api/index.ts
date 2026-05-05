import { api } from '@/shared/api/client'
import type {
  CUser,
  CUserDetail,
  UserListParams,
  UserUpdatePayload,
} from '../types'

const PREFIX = '/admin/users'

export const userApi = {
  list: (params: UserListParams = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
    })
    const qs = q.toString()
    return api.get<{ items: CUser[]; total: number }>(`${PREFIX}${qs ? '?' + qs : ''}`)
  },
  get: (id: number) => api.get<CUserDetail>(`${PREFIX}/${id}`),
  update: (id: number, payload: UserUpdatePayload) =>
    api.patch<CUser>(`${PREFIX}/${id}`, payload),
}
