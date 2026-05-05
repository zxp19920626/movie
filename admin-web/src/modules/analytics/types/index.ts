export interface StatsOverview {
  period_hours: number
  dau: number
  daa: number
  play_start_count: number
  search_count: number
  ad_pv: number
  upgrade_check_count: number
  new_subscriptions: number
  revenue_estimate: number
}

export interface TrendPoint {
  date: string
  value: number
}

export interface TrendSeries {
  code: string
  label: string
  points: TrendPoint[]
}

export interface StatsTrends {
  days: number
  series: TrendSeries[]
}
