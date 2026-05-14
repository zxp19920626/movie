// 与 backend/app/modules/channel_pack/schemas.py 对齐

export type PopupStrategy =
  | 'once_per_launch'
  | 'once_per_session'
  | 'once_per_day'
  | 'once_per_week'
  | 'once_per_release'
  | 'custom_interval'

export const POPUP_STRATEGY_LABELS: Record<PopupStrategy, string> = {
  once_per_launch: '每次启动提示',
  once_per_session: '每个会话一次',
  once_per_day: '每天一次',
  once_per_week: '每周一次',
  once_per_release: '此版本仅一次',
  custom_interval: '自定义间隔',
}

export type SigningStrategy = 'walle' | 'none' | 'play_signed'

// PopupButton type 5 枚举（与 backend/app/modules/channel_pack/schemas.py:63 严格一致）
export type PopupButtonType = 'browser' | 'playstore' | 'inapp_apk' | 'deeplink' | 'none'

export const POPUP_BUTTON_TYPES: PopupButtonType[] = [
  'browser',
  'playstore',
  'inapp_apk',
  'deeplink',
  'none',
]

export const POPUP_BUTTON_TYPE_LABELS: Record<PopupButtonType, string> = {
  browser: '跳浏览器',
  playstore: '跳 Google Play',
  inapp_apk: '应用内下载 APK',
  deeplink: '应用内跳转',
  none: '无跳转（关闭）',
}

export type PopupButtonStyle = 'primary' | 'secondary' | 'danger'

export interface PopupButton {
  id: string
  type: PopupButtonType
  text_i18n: Record<string, string>
  url_i18n: Record<string, string> | null
  style?: PopupButtonStyle | null
  target?: Record<string, string> | null
}

// Host 校验正则（与 backend/app/modules/channel_pack/schemas.py:HOST_REGEX 一致）
export const HOST_REGEX = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/

export interface CpApp {
  id: number
  tenant_uuid: string
  name: string
  package_name: string
  owner_admin_user_id: number
  status: string
  allowed_upgrade_hosts: string[]
  created_at: string
}

export interface AppCreatePayload {
  name: string
  package_name: string
  owner_admin_user_id?: number | null
}

export interface AppCreateResponse {
  app: CpApp
  api_key: string
  hmac_secret: string
}

export interface CpChannel {
  id: number
  app_id: number
  code: string
  name: string
  is_play_store: boolean
  signing_strategy: SigningStrategy
  enabled: boolean
  priority: number
}

export interface ChannelCreatePayload {
  code: string
  name: string
  is_play_store: boolean
  signing_strategy: SigningStrategy
  enabled: boolean
  priority: number
}

export interface CpVersion {
  id: number
  app_id: number
  version_code: number
  version_name: string
  master_apk_sha256: string
  master_apk_size: number
  min_supported_version_code: number
  changelog_i18n: Record<string, string>
  status: 'draft' | 'signing' | 'ready' | 'archived'
  uploaded_at: string
  released_at: string | null
}

export interface CpRule {
  id: number
  app_id: number
  name: string
  enabled: boolean
  version_code_min: number
  version_code_max: number
  channel_codes: string[]
  country_codes: string[]
  device_id_hash_mod_min: number
  device_id_hash_mod_max: number
  target_version_code: number
  is_force: boolean
  can_skip: boolean
  popup_strategy: PopupStrategy
  popup_interval_hours: number | null
  popup_title_i18n: Record<string, string>
  popup_content_i18n: Record<string, string>
  confirm_text_i18n: Record<string, string>
  cancel_text_i18n: Record<string, string>
  popup_buttons: PopupButton[]
  priority: number
  effective_from: string | null
  effective_to: string | null
  created_at: string
}

export interface RuleCreatePayload {
  name: string
  enabled: boolean
  version_code_min: number
  version_code_max: number
  channel_codes: string[]
  country_codes: string[]
  device_id_hash_mod_min: number
  device_id_hash_mod_max: number
  target_version_code: number
  is_force: boolean
  can_skip: boolean
  popup_strategy: PopupStrategy
  popup_interval_hours: number | null
  popup_title_i18n: Record<string, string>
  popup_content_i18n: Record<string, string>
  confirm_text_i18n: Record<string, string>
  cancel_text_i18n: Record<string, string>
  popup_buttons: PopupButton[]
  priority: number
  effective_from: string | null
  effective_to: string | null
}

export interface CpSigningJob {
  id: number
  app_id: number
  version_code: number
  channel_code: string
  status: 'pending' | 'running' | 'success' | 'failed'
  output_oss_key: string
  output_sha256: string
  output_size: number
  attempts: number
  last_error: string
  started_at: string | null
  finished_at: string | null
}

export interface RulePreviewRequest {
  version_code: number
  channel: string
  country: string
  device_id: string
}

export interface RulePreviewResponse {
  has_update: boolean
  matched_rule_id: number | null
  matched_rule_name: string | null
  target_version_code: number | null
  is_force: boolean | null
  debug_steps: string[]
}

// 目标用户区域常用国家码（PROMPT.md C1+C3）
export const TARGET_COUNTRIES: { code: string; label: string }[] = [
  { code: 'ID', label: '印尼' },
  { code: 'VN', label: '越南' },
  { code: 'PH', label: '菲律宾' },
  { code: 'TH', label: '泰国' },
  { code: 'SA', label: '沙特' },
  { code: 'AE', label: '阿联酋' },
  { code: 'EG', label: '埃及' },
  { code: 'BR', label: '巴西' },
  { code: 'MX', label: '墨西哥' },
  { code: 'AR', label: '阿根廷' },
  { code: 'NG', label: '尼日利亚' },
  { code: 'ZA', label: '南非' },
]

export const I18N_LOCALES: { code: string; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '简体中文' },
  { code: 'id', label: 'Bahasa' },
  { code: 'vi', label: 'Tiếng Việt' },
  { code: 'th', label: 'ไทย' },
  { code: 'pt', label: 'Português' },
  { code: 'es', label: 'Español' },
  { code: 'ar', label: 'العربية' },
  { code: 'fr', label: 'Français' },
  { code: 'ja', label: '日本語' },
]
