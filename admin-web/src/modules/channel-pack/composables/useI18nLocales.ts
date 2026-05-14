// 共享 helper：i18n locales 增删（弹窗 4 字段 + PopupButton text/url）
// 约束：'en' 是兜底语言，不允许删除（与后端 RuleOut 默认期望一致）
import { I18N_LOCALES } from '../types'

export const I18N_FALLBACK_LOCALE = 'en'

/**
 * 给定一个 i18n record，返回可新增的 locale 候选列表（已存在的过滤掉）。
 */
export function availableLocales(record: Record<string, string>): { code: string; label: string }[] {
  const existing = new Set(Object.keys(record))
  return I18N_LOCALES.filter((l) => !existing.has(l.code))
}

/**
 * 给若干个 i18n record 合并出所有出现过的 locale（去重，en 永远在第一位）。
 * 用于把 popup_title_i18n / popup_content_i18n / confirm_text_i18n / cancel_text_i18n 的 tab 集合到一起显示。
 */
export function collectActiveLocales(records: Array<Record<string, string> | null | undefined>): string[] {
  const set = new Set<string>()
  set.add(I18N_FALLBACK_LOCALE)
  for (const r of records) {
    if (!r) continue
    for (const k of Object.keys(r)) set.add(k)
  }
  // en 在第一，其它按 I18N_LOCALES 顺序
  const ordered = I18N_LOCALES.filter((l) => set.has(l.code)).map((l) => l.code)
  // 兜底：有出现过、但不在 I18N_LOCALES 候选里的，也保留到末尾
  for (const c of set) if (!ordered.includes(c)) ordered.push(c)
  return ordered
}

/**
 * 在 record 上新增一个 locale（值为空串）。返回新 record。
 */
export function addLocale(record: Record<string, string>, code: string): Record<string, string> {
  if (record[code] !== undefined) return record
  return { ...record, [code]: '' }
}

/**
 * 从 record 删除一个 locale。'en' 不允许删除。
 */
export function removeLocale(record: Record<string, string>, code: string): Record<string, string> {
  if (code === I18N_FALLBACK_LOCALE) return record
  if (record[code] === undefined) return record
  const next = { ...record }
  delete next[code]
  return next
}
