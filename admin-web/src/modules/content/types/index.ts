export type I18nMap = Record<string, string>

export interface CtCategory {
  id: number
  code: string
  name_i18n: I18nMap
  parent_id: number | null
  sort_order: number
  status: 'active' | 'archived'
  created_at: string
}

export interface CategoryListResp {
  items: CtCategory[]
  total: number
}

export interface CategoryCreatePayload {
  code: string
  name_i18n: I18nMap
  parent_id?: number | null
  sort_order?: number
}

export interface CategoryUpdatePayload {
  name_i18n?: I18nMap
  parent_id?: number | null
  sort_order?: number
  status?: 'active' | 'archived'
}

export interface CtVideo {
  id: number
  code: string
  title_i18n: I18nMap
  description_i18n: I18nMap
  type: 'movie' | 'series' | 'short'
  category_id: number | null
  tags: string[]
  score: number | null
  rating: string
  release_year: number | null
  release_date: string | null
  duration_min: number | null
  director: string
  cast_list: string[]
  studio: string
  cover_url: string
  poster_url: string
  trailer_url: string
  vod_file_id: string | null
  vod_status: 'pending' | 'transcoding' | 'ready' | 'failed'
  vod_synced_at: string | null
  required_tier: 'free' | 'vip1' | 'vip2'
  status: 'draft' | 'online' | 'offline' | 'archived'
  secondary_review_status: 'draft' | 'pending' | 'approved' | 'rejected'
  secondary_reviewed_at: string | null
  featured: boolean
  trending: boolean
  views: number
  recommend_priority: number
  created_at: string
  updated_at: string
}

export interface VideoListResp {
  items: CtVideo[]
  total: number
}

export interface VideoListParams {
  status?: string
  secondary_review_status?: string
  category_id?: number
  q?: string
  limit?: number
  offset?: number
}

export interface VideoCreatePayload {
  code: string
  title_i18n: I18nMap
  description_i18n: I18nMap
  type?: string
  category_id?: number | null
  tags?: string[]
  rating?: string
  release_year?: number | null
  duration_min?: number | null
  director?: string
  cast_list?: string[]
  studio?: string
  cover_url?: string
  poster_url?: string
  trailer_url?: string
  vod_file_id?: string | null
  required_tier?: string
}

export interface VideoUpdatePayload extends Partial<VideoCreatePayload> {
  status?: 'draft' | 'online' | 'offline' | 'archived'
  featured?: boolean
  trending?: boolean
  recommend_priority?: number
  score?: number | null
}

export interface RegionVisibilityResp {
  video_id: number
  visible_countries: string[]
  hidden_countries: string[]
}

export interface RegionVisibilityEntry {
  country_code: string
  visible: boolean
}

export interface SecondaryReviewActionPayload {
  action: 'submit' | 'approve' | 'reject'
  note?: string
}

export interface SecondaryReviewResp {
  video_id: number
  secondary_review_status: string
  secondary_reviewed_by: number | null
  secondary_reviewed_at: string | null
  secondary_review_note: string
}
