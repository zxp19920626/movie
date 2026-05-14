import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../api', () => ({
  cpApi: {
    listRules: vi.fn(),
    listChannels: vi.fn(),
    listVersions: vi.fn(),
    createRule: vi.fn(),
    updateRule: vi.fn(),
    deleteRule: vi.fn(),
    previewRule: vi.fn(),
  },
}))

import RulesView from '../RulesView.vue'
import { cpApi } from '../../api'
import { useCpStore } from '../../stores/cp'
import { ElMessage } from 'element-plus'
import type { CpApp, CpChannel, CpRule, CpVersion, PopupButton, RuleCreatePayload } from '../../types'

const app: CpApp = {
  id: 1,
  tenant_uuid: 'u',
  name: 'Movie',
  package_name: 'com.movie',
  owner_admin_user_id: 1,
  status: 'active',
  allowed_upgrade_hosts: ['cdn.example.com'],
  created_at: '2026-01-01T00:00:00Z',
}

const channels: CpChannel[] = [
  {
    id: 1,
    app_id: 1,
    code: 'gp',
    name: 'Play Store',
    is_play_store: true,
    signing_strategy: 'play_signed',
    enabled: true,
    priority: 20,
  },
  {
    id: 2,
    app_id: 1,
    code: 'apk',
    name: 'Direct APK',
    is_play_store: false,
    signing_strategy: 'walle',
    enabled: true,
    priority: 10,
  },
]

const versions: CpVersion[] = [
  {
    id: 1,
    app_id: 1,
    version_code: 100,
    version_name: '1.0.0',
    master_apk_sha256: 'a'.repeat(64),
    master_apk_size: 1024,
    min_supported_version_code: 1,
    changelog_i18n: { en: 'v1' },
    status: 'ready',
    uploaded_at: '2026-01-01T00:00:00Z',
    released_at: null,
  },
]

function makeRule(overrides: Partial<CpRule> = {}): CpRule {
  return {
    id: 1,
    app_id: 1,
    name: 'r1',
    enabled: true,
    version_code_min: 1,
    version_code_max: 99,
    channel_codes: [],
    country_codes: [],
    device_id_hash_mod_min: 0,
    device_id_hash_mod_max: 99,
    target_version_code: 100,
    is_force: false,
    can_skip: true,
    popup_strategy: 'once_per_session',
    popup_interval_hours: null,
    popup_title_i18n: { en: 'T' },
    popup_content_i18n: { en: 'C' },
    confirm_text_i18n: { en: 'OK' },
    cancel_text_i18n: { en: 'Cancel' },
    popup_buttons: [],
    priority: 10,
    effective_from: null,
    effective_to: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

async function mountView(rules: CpRule[] = []) {
  setActivePinia(createPinia())
  const store = useCpStore()
  store.apps = [app]
  store.setCurrentApp(app.id)
  ;(cpApi.listRules as ReturnType<typeof vi.fn>).mockResolvedValue({ items: rules, total: rules.length })
  ;(cpApi.listChannels as ReturnType<typeof vi.fn>).mockResolvedValue({ items: channels, total: channels.length })
  ;(cpApi.listVersions as ReturnType<typeof vi.fn>).mockResolvedValue({ items: versions, total: versions.length })
  const wrapper = mount(RulesView, { attachTo: document.body })
  await flushPromises()
  return { wrapper, store }
}

interface RulesViewVm {
  form: RuleCreatePayload
  openCreate: () => void
  openEdit: (row: CpRule) => void
  submit: () => Promise<void>
  items: CpRule[]
  popupEditorRef: { validationErrors: string[] } | null
  isPlayStoreHit: boolean
  activeLocales: string[]
  addLocaleDialog: { visible: boolean; selected: string; candidates: { code: string; label: string }[] }
  openAddLocaleDialog: () => void
  confirmAddLocale: () => void
  removeRuleLocale: (code: string) => void
}

describe('RulesView popup_buttons integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submit_blocked_when_editor_has_play_inapp_apk_error', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as RulesViewVm
    vm.openCreate()
    await flushPromises()
    vm.form.name = '强升'
    vm.form.target_version_code = 100
    vm.form.channel_codes = ['gp'] // play 渠道
    const badButton: PopupButton = {
      id: 'go',
      type: 'inapp_apk',
      text_i18n: { en: 'Install' },
      url_i18n: { en: 'https://cdn.example.com/x.apk' },
      style: null,
      target: null,
    }
    vm.form.popup_buttons = [badButton]
    await flushPromises()
    expect(vm.isPlayStoreHit).toBe(true)
    expect(vm.popupEditorRef?.validationErrors.some((e) => /inapp_apk/.test(e))).toBe(true)

    const errSpy = vi.spyOn(ElMessage, 'error')
    await vm.submit()
    expect(cpApi.createRule).not.toHaveBeenCalled()
    expect(errSpy).toHaveBeenCalled()
  })

  it('submit_passes_when_no_validation_errors', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as RulesViewVm
    vm.openCreate()
    await flushPromises()
    vm.form.name = '正常升级'
    vm.form.target_version_code = 100
    vm.form.channel_codes = ['apk'] // 非 play
    vm.form.popup_buttons = [
      {
        id: 'go',
        type: 'browser',
        text_i18n: { en: 'Open' },
        url_i18n: { en: 'https://cdn.example.com/landing' },
        style: null,
        target: null,
      },
    ]
    await flushPromises()
    expect(vm.isPlayStoreHit).toBe(false)
    expect(vm.popupEditorRef?.validationErrors).toEqual([])

    ;(cpApi.createRule as ReturnType<typeof vi.fn>).mockResolvedValue(makeRule({ id: 7 }))
    await vm.submit()
    expect(cpApi.createRule).toHaveBeenCalledTimes(1)
    const [, payload] = (cpApi.createRule as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(payload.popup_buttons).toHaveLength(1)
    expect(payload.popup_buttons[0].id).toBe('go')
  })

  it('table_shows_popup_buttons_count', async () => {
    const r1 = makeRule({ id: 1, name: 'no-btns', popup_buttons: [] })
    const r2 = makeRule({
      id: 2,
      name: 'two-btns',
      popup_buttons: [
        {
          id: 'a',
          type: 'browser',
          text_i18n: { en: 'A' },
          url_i18n: { en: 'https://cdn.example.com/a' },
          style: null,
          target: null,
        },
        {
          id: 'b',
          type: 'none',
          text_i18n: { en: 'B' },
          url_i18n: null,
          style: null,
          target: null,
        },
      ],
    })
    const { wrapper } = await mountView([r1, r2])
    const vm = wrapper.vm as unknown as RulesViewVm
    expect(vm.items).toHaveLength(2)
    // 表格列 "按钮数" 渲染
    const html = wrapper.html()
    expect(html).toContain('按钮数')
    // 两行的 tag 值（0 和 2）
    const rowsHtml = wrapper.findAll('tr')
    // 找包含 popup-buttons-count-col 的单元格
    const countCells = wrapper.findAll('.popup-buttons-count-col')
    expect(countCells.length).toBeGreaterThanOrEqual(2)
    const counts = countCells.map((c) => c.text().trim()).filter((t) => /^\d+$/.test(t))
    expect(counts).toContain('0')
    expect(counts).toContain('2')
    expect(rowsHtml.length).toBeGreaterThanOrEqual(2)
  })

  it('isPlayStoreHit_apply_to_all_when_play_channel_exists', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as RulesViewVm
    vm.openCreate()
    await flushPromises()
    vm.form.channel_codes = [] // apply to all
    await flushPromises()
    expect(vm.isPlayStoreHit).toBe(true) // 因 channels 含 play
  })

  it('add_locale_dialog_extends_all_four_i18n_records', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as RulesViewVm
    vm.openCreate()
    await flushPromises()
    vm.openAddLocaleDialog()
    await flushPromises()
    expect(vm.addLocaleDialog.visible).toBe(true)
    expect(vm.addLocaleDialog.candidates.length).toBeGreaterThan(0)
    vm.addLocaleDialog.selected = 'zh'
    vm.confirmAddLocale()
    await flushPromises()
    expect(vm.form.popup_title_i18n).toHaveProperty('zh')
    expect(vm.form.popup_content_i18n).toHaveProperty('zh')
    expect(vm.form.confirm_text_i18n).toHaveProperty('zh')
    expect(vm.form.cancel_text_i18n).toHaveProperty('zh')
    expect(vm.addLocaleDialog.visible).toBe(false)
  })

  it('remove_rule_locale_drops_from_all_four_records_but_keeps_en', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as RulesViewVm
    vm.openCreate()
    await flushPromises()
    vm.form.popup_title_i18n = { en: 'T', zh: '标题' }
    vm.form.popup_content_i18n = { en: 'C', zh: '内容' }
    vm.form.confirm_text_i18n = { en: 'OK', zh: '确认' }
    vm.form.cancel_text_i18n = { en: 'Cancel', zh: '取消' }
    vm.removeRuleLocale('zh')
    await flushPromises()
    expect(vm.form.popup_title_i18n).not.toHaveProperty('zh')
    expect(vm.form.popup_content_i18n).not.toHaveProperty('zh')
    expect(vm.form.confirm_text_i18n).not.toHaveProperty('zh')
    expect(vm.form.cancel_text_i18n).not.toHaveProperty('zh')

    vm.removeRuleLocale('en') // 不允许
    await flushPromises()
    expect(vm.form.popup_title_i18n).toHaveProperty('en')
  })
})
