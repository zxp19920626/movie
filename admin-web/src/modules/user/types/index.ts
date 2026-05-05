// 与 backend/app/modules/user/routers/admin.py 对齐

export interface CUser {
  id: number
  uuid: string
  email: string | null
  phone: string | null
  country_code: string | null
  display_name: string
  avatar_url: string | null
  status: 'active' | 'suspended' | 'deleted'
  country: string | null
  preferred_language: string
  app_id: number | null
  registered_at: string | null
  last_active_at: string | null
}

export interface CUserDevice {
  id: number
  device_id: string
  app_id: number | null
  platform: string
  app_version: string | null
  channel: string | null
  country: string | null
  last_seen_at: string
}

export interface CUserDetail extends CUser {
  devices: CUserDevice[]
}

export interface UserListParams {
  search?: string
  status?: 'active' | 'suspended' | 'deleted'
  app_id?: number
  limit?: number
  offset?: number
}

export interface UserUpdatePayload {
  display_name?: string
  status?: 'active' | 'suspended' | 'deleted'
  preferred_language?: string
  country?: string
}
