import { api } from '@/shared/api/client'
import type { StatsOverview, StatsTrends } from '../types'

export const statsApi = {
  overview: (period_hours = 24) =>
    api.get<StatsOverview>(`/admin/stats/overview?period_hours=${period_hours}`),
  trends: (days = 30) => api.get<StatsTrends>(`/admin/stats/trends?days=${days}`),
}
