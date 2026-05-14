import { describe, it, expect } from 'vitest'
import {
  addLocale,
  removeLocale,
  collectActiveLocales,
  availableLocales,
  I18N_FALLBACK_LOCALE,
} from '../useI18nLocales'

describe('useI18nLocales', () => {
  it('add_locale_appends_tab_with_empty_values', () => {
    const r = { en: 'hi' }
    const next = addLocale(r, 'zh')
    expect(next).toEqual({ en: 'hi', zh: '' })
    // 不破坏原对象
    expect(r).toEqual({ en: 'hi' })
  })

  it('add_locale_is_idempotent_when_code_already_exists', () => {
    const r = { en: 'hi', zh: '你好' }
    const next = addLocale(r, 'zh')
    expect(next).toBe(r)
  })

  it('remove_locale_drops_key_from_record', () => {
    const r = { en: 'hi', zh: '你好', vi: 'xin chao' }
    const next = removeLocale(r, 'zh')
    expect(next).toEqual({ en: 'hi', vi: 'xin chao' })
    expect(r).toHaveProperty('zh') // 原对象保留
  })

  it('cannot_remove_en_locale', () => {
    const r = { en: 'hi', zh: '你好' }
    const next = removeLocale(r, I18N_FALLBACK_LOCALE)
    expect(next).toBe(r) // 直接返回原对象
    expect(next).toHaveProperty('en')
  })

  it('remove_locale_on_missing_key_returns_same_object', () => {
    const r = { en: 'hi' }
    const next = removeLocale(r, 'zh')
    expect(next).toBe(r)
  })

  it('collect_active_locales_union_with_en_first', () => {
    const a = { en: 'a', zh: 'b' }
    const b = { en: 'a', vi: 'c' }
    const got = collectActiveLocales([a, b, null, undefined])
    expect(got[0]).toBe('en')
    expect(got).toContain('zh')
    expect(got).toContain('vi')
  })

  it('collect_active_locales_handles_empty_input', () => {
    expect(collectActiveLocales([])).toEqual(['en'])
  })

  it('available_locales_excludes_existing', () => {
    const existing = { en: 'a', zh: 'b' }
    const got = availableLocales(existing)
    const codes = got.map((g) => g.code)
    expect(codes).not.toContain('en')
    expect(codes).not.toContain('zh')
    expect(codes.length).toBeGreaterThan(0)
  })
})
