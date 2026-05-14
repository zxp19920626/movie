import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PopupButtonEditor from '../PopupButtonEditor.vue'
import type { PopupButton } from '../../types'

function makeButton(overrides: Partial<PopupButton> = {}): PopupButton {
  return {
    id: 'btn_1',
    type: 'browser',
    text_i18n: { en: 'Update' },
    url_i18n: { en: 'https://cdn.example.com/x.apk' },
    style: null,
    target: null,
    ...overrides,
  }
}

interface EditorInstance {
  validationErrors: string[]
  addButton: () => void
  moveButton: (idx: number, dir: -1 | 1) => void
  changeType: (idx: number, t: PopupButton['type']) => void
  updateTextI18n: (idx: number, code: string, value: string) => void
  updateUrlI18n: (idx: number, code: string, value: string) => void
  updateField: <K extends keyof PopupButton>(idx: number, key: K, value: PopupButton[K]) => void
  addButtonLocale: (idx: number, code: string) => void
  removeButtonLocale: (idx: number, code: string) => void
  removeButton: (idx: number) => Promise<void>
}

function mountEditor(props: {
  modelValue: PopupButton[]
  allowedHosts?: string[]
  isPlayStore?: boolean
  locales?: string[]
}) {
  return mount(PopupButtonEditor, {
    props: {
      allowedHosts: ['cdn.example.com'],
      isPlayStore: false,
      locales: ['en'],
      ...props,
    },
    attachTo: document.body,
  })
}

function vmOf(wrapper: ReturnType<typeof mountEditor>): EditorInstance {
  return wrapper.vm as unknown as EditorInstance
}

describe('PopupButtonEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('mount_with_empty_list_shows_add_button_enabled', async () => {
    const wrapper = mountEditor({ modelValue: [] })
    await flushPromises()
    const html = wrapper.html()
    expect(html).toContain('+ 添加按钮')
    // 找到 add 按钮（el-button stub 会渲染 button 元素或 el-button 组件）
    const btns = wrapper.findAll('button')
    const addBtn = btns.find((b) => b.text().includes('+ 添加按钮'))
    expect(addBtn).toBeTruthy()
    expect(addBtn!.attributes('disabled')).toBeUndefined()
  })

  it('add_button_appends_with_default_browser_type', async () => {
    const wrapper = mountEditor({ modelValue: [] })
    vmOf(wrapper).addButton()
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    const last = emitted![emitted!.length - 1][0] as PopupButton[]
    expect(last).toHaveLength(1)
    expect(last[0].type).toBe('browser')
    expect(last[0].text_i18n).toEqual({ en: '' })
    expect(last[0].url_i18n).toEqual({ en: '' })
  })

  it('add_disabled_when_already_5_buttons', async () => {
    const five = Array.from({ length: 5 }, (_, i) =>
      makeButton({ id: `btn_${i + 1}` }),
    )
    const wrapper = mountEditor({ modelValue: five })
    await flushPromises()
    // 不能再增加
    vmOf(wrapper).addButton()
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    // 按钮上有 disabled 属性
    const btns = wrapper.findAll('button')
    const addBtn = btns.find((b) => b.text().includes('+ 添加按钮'))
    expect(addBtn).toBeTruthy()
    expect(addBtn!.attributes('disabled')).toBeDefined()
  })

  it('change_type_to_none_hides_url_input_and_clears_url_i18n', async () => {
    const btn = makeButton()
    const wrapper = mountEditor({ modelValue: [btn] })
    vmOf(wrapper).changeType(0, 'none')
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last[0].type).toBe('none')
    expect(last[0].url_i18n).toBeNull()
  })

  it('change_type_from_none_to_browser_shows_url_input', async () => {
    const btn = makeButton({ type: 'none', url_i18n: null })
    const wrapper = mountEditor({ modelValue: [btn] })
    vmOf(wrapper).changeType(0, 'browser')
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last[0].type).toBe('browser')
    expect(last[0].url_i18n).toEqual({ en: '' })
  })

  it('remove_button_emits_shortened_array', async () => {
    const wrapper = mountEditor({
      modelValue: [makeButton({ id: 'a' }), makeButton({ id: 'b' })],
    })
    await vmOf(wrapper).removeButton(0)
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last).toHaveLength(1)
    expect(last[0].id).toBe('b')
  })

  it('edit_text_i18n_emits_updated_value', async () => {
    const wrapper = mountEditor({ modelValue: [makeButton()] })
    vmOf(wrapper).updateTextI18n(0, 'en', 'Install now')
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last[0].text_i18n.en).toBe('Install now')
  })

  it('validation_play_store_inapp_apk_shows_red_alert', async () => {
    const wrapper = mountEditor({
      isPlayStore: true,
      modelValue: [makeButton({ type: 'inapp_apk' })],
    })
    await flushPromises()
    const errs = vmOf(wrapper).validationErrors
    expect(errs.some((e) => /inapp_apk/.test(e))).toBe(true)
    expect(wrapper.html()).toContain('inapp_apk')
  })

  it('validation_host_not_in_whitelist_shows_red_alert', async () => {
    const wrapper = mountEditor({
      allowedHosts: ['cdn.example.com'],
      modelValue: [
        makeButton({
          url_i18n: { en: 'https://evil.com/x.apk' },
        }),
      ],
    })
    await flushPromises()
    const errs = vmOf(wrapper).validationErrors
    expect(errs.some((e) => /白名单/.test(e) && /evil\.com/.test(e))).toBe(true)
  })

  it('validation_non_https_url_shows_red_alert', async () => {
    const wrapper = mountEditor({
      allowedHosts: ['cdn.example.com'],
      modelValue: [
        makeButton({
          url_i18n: { en: 'http://cdn.example.com/x.apk' },
        }),
      ],
    })
    await flushPromises()
    const errs = vmOf(wrapper).validationErrors
    expect(errs.some((e) => /https/.test(e))).toBe(true)
  })

  it('validation_duplicate_id_shows_red_alert', async () => {
    const wrapper = mountEditor({
      modelValue: [
        makeButton({ id: 'same' }),
        makeButton({ id: 'same' }),
      ],
    })
    await flushPromises()
    const errs = vmOf(wrapper).validationErrors
    expect(errs.some((e) => /重复/.test(e))).toBe(true)
  })

  it('validation_clean_passes_with_valid_data', async () => {
    const wrapper = mountEditor({
      modelValue: [makeButton({ id: 'a' }), makeButton({ id: 'b' })],
    })
    await flushPromises()
    expect(vmOf(wrapper).validationErrors).toEqual([])
  })

  it('move_button_up_down_reorders', async () => {
    const wrapper = mountEditor({
      modelValue: [
        makeButton({ id: 'a' }),
        makeButton({ id: 'b' }),
        makeButton({ id: 'c' }),
      ],
    })
    // 注意：props.modelValue 在 emit 之后不会因父组件双向绑定而自动变化（这里没父）；
    // 每次 moveButton 都基于初始 props 计算
    vmOf(wrapper).moveButton(2, -1) // 'c' 上移 → ['a','c','b']
    await flushPromises()
    let emitted = wrapper.emitted('update:modelValue')!
    let last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last.map((b) => b.id)).toEqual(['a', 'c', 'b'])

    vmOf(wrapper).moveButton(0, 1) // 'a' 下移 → ['b','a','c']
    await flushPromises()
    emitted = wrapper.emitted('update:modelValue')!
    last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last.map((b) => b.id)).toEqual(['b', 'a', 'c'])
  })

  it('move_button_out_of_bounds_is_noop', async () => {
    const wrapper = mountEditor({
      modelValue: [makeButton({ id: 'a' }), makeButton({ id: 'b' })],
    })
    vmOf(wrapper).moveButton(0, -1) // 第一个再上移 noop
    vmOf(wrapper).moveButton(1, 1) // 最后一个再下移 noop
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('add_button_locale_extends_text_and_url_i18n', async () => {
    const wrapper = mountEditor({
      modelValue: [
        makeButton({
          text_i18n: { en: 'Update' },
          url_i18n: { en: 'https://cdn.example.com/x.apk' },
        }),
      ],
    })
    vmOf(wrapper).addButtonLocale(0, 'zh')
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last[0].text_i18n).toEqual({ en: 'Update', zh: '' })
    expect(last[0].url_i18n).toEqual({ en: 'https://cdn.example.com/x.apk', zh: '' })
  })

  it('remove_button_locale_drops_text_and_url_i18n', async () => {
    const wrapper = mountEditor({
      modelValue: [
        makeButton({
          text_i18n: { en: 'Update', zh: '更新' },
          url_i18n: { en: 'https://cdn.example.com/x.apk', zh: 'https://cdn.example.com/y.apk' },
        }),
      ],
    })
    vmOf(wrapper).removeButtonLocale(0, 'zh')
    await flushPromises()
    const emitted = wrapper.emitted('update:modelValue')!
    const last = emitted[emitted.length - 1][0] as PopupButton[]
    expect(last[0].text_i18n).toEqual({ en: 'Update' })
    expect(last[0].url_i18n).toEqual({ en: 'https://cdn.example.com/x.apk' })
  })

  it('cannot_remove_en_locale_from_button', async () => {
    const wrapper = mountEditor({
      modelValue: [makeButton({ text_i18n: { en: 'Update', zh: '更新' } })],
    })
    vmOf(wrapper).removeButtonLocale(0, 'en')
    await flushPromises()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
