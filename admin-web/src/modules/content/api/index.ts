import { api } from '@/shared/api/client'
import type {
  CategoryCreatePayload,
  CategoryListResp,
  CategoryUpdatePayload,
  CtCategory,
  CtVideo,
  RegionVisibilityEntry,
  RegionVisibilityResp,
  SecondaryReviewActionPayload,
  SecondaryReviewResp,
  VideoCreatePayload,
  VideoListParams,
  VideoListResp,
  VideoUpdatePayload,
} from '../types'

const PREFIX = '/admin/content'

function toQuery(params: Record<string, unknown>): string {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  })
  const qs = q.toString()
  return qs ? `?${qs}` : ''
}

// ===== Categories =====
export const categoryApi = {
  list: (limit = 100, offset = 0) =>
    api.get<CategoryListResp>(`${PREFIX}/categories${toQuery({ limit, offset })}`),
  create: (payload: CategoryCreatePayload) =>
    api.post<CtCategory>(`${PREFIX}/categories`, payload),
  update: (id: number, payload: CategoryUpdatePayload) =>
    api.patch<CtCategory>(`${PREFIX}/categories/${id}`, payload),
  delete: (id: number) => api.del<void>(`${PREFIX}/categories/${id}`),
}

// ===== Videos =====
export const videoApi = {
  list: (params: VideoListParams = {}) =>
    api.get<VideoListResp>(`${PREFIX}/videos${toQuery(params as Record<string, unknown>)}`),
  get: (id: number) => api.get<CtVideo>(`${PREFIX}/videos/${id}`),
  create: (payload: VideoCreatePayload) =>
    api.post<CtVideo>(`${PREFIX}/videos`, payload),
  update: (id: number, payload: VideoUpdatePayload) =>
    api.put<CtVideo>(`${PREFIX}/videos/${id}`, payload),
  delete: (id: number) => api.del<void>(`${PREFIX}/videos/${id}`),
  // region-visibility
  getRegions: (id: number) =>
    api.get<RegionVisibilityResp>(`${PREFIX}/videos/${id}/region-visibility`),
  setRegions: (id: number, entries: RegionVisibilityEntry[]) =>
    api.post<RegionVisibilityResp>(`${PREFIX}/videos/${id}/region-visibility`, { entries }),
  // secondary review
  review: (id: number, payload: SecondaryReviewActionPayload) =>
    api.post<SecondaryReviewResp>(`${PREFIX}/videos/${id}/secondary-review`, payload),
}
