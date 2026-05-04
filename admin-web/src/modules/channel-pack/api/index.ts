// channel_pack 模块 API 客户端
import { api } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'
import type {
  AppCreatePayload,
  AppCreateResponse,
  ChannelCreatePayload,
  CpApp,
  CpChannel,
  CpRule,
  CpSigningJob,
  CpVersion,
  RuleCreatePayload,
  RulePreviewRequest,
  RulePreviewResponse,
} from '../types'

const PREFIX = '/admin/cp'

export const cpApi = {
  // ===== Apps =====
  listApps: () => api.get<{ items: CpApp[]; total: number }>(`${PREFIX}/apps`),
  createApp: (payload: AppCreatePayload) =>
    api.post<AppCreateResponse>(`${PREFIX}/apps`, payload),
  getApp: (appId: number) => api.get<CpApp>(`${PREFIX}/apps/${appId}`),
  updateApp: (appId: number, payload: Partial<AppCreatePayload>) =>
    api.patch<CpApp>(`${PREFIX}/apps/${appId}`, payload),
  deleteApp: (appId: number) => api.del(`${PREFIX}/apps/${appId}`),
  regenerateKeys: (appId: number) =>
    api.post<{ api_key: string; hmac_secret: string }>(`${PREFIX}/apps/${appId}/regenerate-keys`),

  // ===== Channels =====
  listChannels: (appId: number) =>
    api.get<{ items: CpChannel[]; total: number }>(`${PREFIX}/apps/${appId}/channels`),
  createChannel: (appId: number, payload: ChannelCreatePayload) =>
    api.post<CpChannel>(`${PREFIX}/apps/${appId}/channels`, payload),
  updateChannel: (appId: number, id: number, payload: Partial<ChannelCreatePayload>) =>
    api.patch<CpChannel>(`${PREFIX}/apps/${appId}/channels/${id}`, payload),
  deleteChannel: (appId: number, id: number) =>
    api.del(`${PREFIX}/apps/${appId}/channels/${id}`),

  // ===== Versions =====
  listVersions: (appId: number) =>
    api.get<{ items: CpVersion[]; total: number }>(`${PREFIX}/apps/${appId}/versions`),
  uploadVersion: async (
    appId: number,
    file: File,
    meta: { version_code: number; version_name: string; min_supported_version_code: number; changelog_i18n: Record<string, string> },
    onProgress?: (pct: number) => void,
  ): Promise<CpVersion> => {
    const auth = useAuthStore()
    const fd = new FormData()
    fd.append('apk_file', file)
    fd.append('version_code', String(meta.version_code))
    fd.append('version_name', meta.version_name)
    fd.append('min_supported_version_code', String(meta.min_supported_version_code))
    fd.append('changelog_i18n', JSON.stringify(meta.changelog_i18n))
    return new Promise<CpVersion>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `/api/v1${PREFIX}/apps/${appId}/versions`)
      if (auth.token) xhr.setRequestHeader('Authorization', `Bearer ${auth.token}`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
      }
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText)
          if (xhr.status >= 200 && xhr.status < 300) resolve(body)
          else reject(new Error(body.detail || `HTTP ${xhr.status}`))
        } catch {
          reject(new Error(`HTTP ${xhr.status}`))
        }
      }
      xhr.onerror = () => reject(new Error('网络错误'))
      xhr.send(fd)
    })
  },
  finalizeVersion: (appId: number, versionId: number) =>
    api.post<CpVersion>(`${PREFIX}/apps/${appId}/versions/${versionId}/finalize`),
  deleteVersion: (appId: number, versionId: number) =>
    api.del(`${PREFIX}/apps/${appId}/versions/${versionId}`),

  // ===== Rules =====
  listRules: (appId: number) =>
    api.get<{ items: CpRule[]; total: number }>(`${PREFIX}/apps/${appId}/rules`),
  createRule: (appId: number, payload: RuleCreatePayload) =>
    api.post<CpRule>(`${PREFIX}/apps/${appId}/rules`, payload),
  updateRule: (appId: number, id: number, payload: Partial<RuleCreatePayload>) =>
    api.patch<CpRule>(`${PREFIX}/apps/${appId}/rules/${id}`, payload),
  deleteRule: (appId: number, id: number) => api.del(`${PREFIX}/apps/${appId}/rules/${id}`),
  previewRule: (appId: number, payload: RulePreviewRequest) =>
    api.post<RulePreviewResponse>(`${PREFIX}/apps/${appId}/rules/preview`, payload),

  // ===== Signing Jobs =====
  listJobs: (appId: number, params: { version_code?: number; status?: string } = {}) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
    })
    const qs = q.toString()
    return api.get<{ items: CpSigningJob[]; total: number }>(
      `${PREFIX}/apps/${appId}/signing-jobs${qs ? '?' + qs : ''}`,
    )
  },
  retryJob: (appId: number, id: number) =>
    api.post<CpSigningJob>(`${PREFIX}/apps/${appId}/signing-jobs/${id}/retry`),
}
