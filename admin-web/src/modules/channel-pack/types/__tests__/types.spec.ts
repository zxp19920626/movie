import { describe, it, expect } from 'vitest'
import {
  HOST_REGEX,
  POPUP_BUTTON_TYPES,
  POPUP_BUTTON_TYPE_LABELS,
  type PopupButtonType,
} from '../index'

describe('PopupButton type constants', () => {
  it('test_POPUP_BUTTON_TYPES_has_5_entries', () => {
    expect(POPUP_BUTTON_TYPES).toHaveLength(5)
    expect(POPUP_BUTTON_TYPES).toEqual([
      'browser',
      'playstore',
      'inapp_apk',
      'deeplink',
      'none',
    ])
  })

  it('test_POPUP_BUTTON_TYPE_LABELS_keys_match', () => {
    const labelKeys = Object.keys(POPUP_BUTTON_TYPE_LABELS).sort()
    const typeValues = ([...POPUP_BUTTON_TYPES] as PopupButtonType[]).sort()
    expect(labelKeys).toEqual(typeValues)
    expect(labelKeys).toHaveLength(5)
    // 全部非空
    for (const k of typeValues) {
      expect(POPUP_BUTTON_TYPE_LABELS[k].length).toBeGreaterThan(0)
    }
  })
})

describe('HOST_REGEX', () => {
  it('test_HOST_REGEX_accepts_valid_and_rejects_invalid', () => {
    const valid = [
      'example.com',
      'a.b.example.com',
      'cdn-1.example.co',
      'x.io',
      'sub.sub2.host-3.com',
    ]
    for (const h of valid) {
      expect(HOST_REGEX.test(h)).toBe(true)
    }

    const invalid = [
      'EXAMPLE.com', // 含大写
      'example', // 无 TLD
      '-example.com', // 段首连字符
      'example-.com', // 段尾连字符
      'example..com', // 空段
      'https://example.com', // 带 scheme
      'example.com/path', // 带 path
      'example.com:443', // 带 port
      ' example.com', // 前置空格
      '',
    ]
    for (const h of invalid) {
      expect(HOST_REGEX.test(h)).toBe(false)
    }
  })
})
