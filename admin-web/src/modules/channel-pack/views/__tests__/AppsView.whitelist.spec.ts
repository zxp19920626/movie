import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'

// 必须先 mock 再 import View
vi.mock('../../api', () => {
  return {
    cpApi: {
      listApps: vi.fn(),
      createApp: vi.fn(),
      updateApp: vi.fn(),
      deleteApp: vi.fn(),
      regenerateKeys: vi.fn(),
    },
  }
})

// element-plus 已在 test-setup.ts 全局 mock，这里无需再 mock

import AppsView from '../AppsView.vue'
import { cpApi } from '../../api'
import { useCpStore } from '../../stores/cp'
import { ApiError } from '@/shared/api/client'
import type { CpApp } from '../../types'

const sampleApp: CpApp = {
  id: 1,
  tenant_uuid: 'uuid-1',
  name: 'Movie',
  package_name: 'com.movie.app',
  owner_admin_user_id: 1,
  status: 'active',
  allowed_upgrade_hosts: ['cdn.example.com', 'old.foo.io'],
  created_at: '2026-01-01T00:00:00Z',
}

async function mountView() {
  setActivePinia(createPinia())
  const store = useCpStore()
  store.apps = [sampleApp]
  ;(cpApi.listApps as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [sampleApp],
    total: 1,
  })
  const wrapper = mount(AppsView, {
    global: {
      stubs: {
        // 不 stub 真实 dialog/table 否则 dom 拿不到，但 teleport 默认会把 dialog 挂到 body
      },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, store }
}

describe('AppsView whitelist dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('dialog_opens_with_current_hosts', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistDialog: boolean
      whitelistHosts: string[]
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    expect(vm.whitelistDialog).toBe(true)
    expect(vm.whitelistHosts).toEqual(['cdn.example.com', 'old.foo.io'])
  })

  it('reject_uppercase_host_shows_red_hint', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistNewHost: string
      whitelistNewHostError: string
      whitelistAddDisabled: boolean
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    vm.whitelistNewHost = 'BAD.Example.com'
    await flushPromises()
    expect(vm.whitelistNewHostError).toMatch(/格式错误/)
    expect(vm.whitelistAddDisabled).toBe(true)
  })

  it('reject_host_with_scheme_https_prefix', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistNewHost: string
      whitelistNewHostError: string
      whitelistAddDisabled: boolean
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    vm.whitelistNewHost = 'https://example.com'
    await flushPromises()
    expect(vm.whitelistNewHostError).toMatch(/格式错误/)
    expect(vm.whitelistAddDisabled).toBe(true)
  })

  it('add_valid_host_appends', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistHosts: string[]
      whitelistNewHost: string
      addHost: () => void
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    vm.whitelistNewHost = 'new.example.org'
    vm.addHost()
    await flushPromises()
    expect(vm.whitelistHosts).toContain('new.example.org')
    expect(vm.whitelistNewHost).toBe('')
  })

  it('remove_host_pops', async () => {
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistHosts: string[]
      removeHost: (idx: number) => void
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    expect(vm.whitelistHosts).toHaveLength(2)
    vm.removeHost(0)
    await flushPromises()
    expect(vm.whitelistHosts).toEqual(['old.foo.io'])
  })

  it('save_calls_updateApp_with_new_hosts', async () => {
    ;(cpApi.updateApp as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...sampleApp,
      allowed_upgrade_hosts: ['cdn.example.com', 'old.foo.io', 'add.io'],
    })
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistNewHost: string
      addHost: () => void
      saveWhitelist: () => Promise<void>
      whitelistDialog: boolean
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    vm.whitelistNewHost = 'add.io'
    vm.addHost()
    await vm.saveWhitelist()
    expect(cpApi.updateApp).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        allowed_upgrade_hosts: ['cdn.example.com', 'old.foo.io', 'add.io'],
      }),
    )
    expect(vm.whitelistDialog).toBe(false)
  })

  it('save_409_shows_affected_rules_alert', async () => {
    ;(cpApi.updateApp as ReturnType<typeof vi.fn>).mockRejectedValue(
      new ApiError('白名单缩短前请清理引用规则', 409, {
        message: '白名单缩短前请清理引用规则',
        removed_hosts: ['old.foo.io'],
        affected_rules: [
          { rule_id: 42, rule_name: '强制升级规则', host: 'old.foo.io' },
        ],
      }),
    )
    const { wrapper } = await mountView()
    const vm = wrapper.vm as unknown as {
      openWhitelist: (app: CpApp) => void
      whitelistHosts: string[]
      removeHost: (idx: number) => void
      saveWhitelist: () => Promise<void>
      whitelistDialog: boolean
      whitelistConflict: { rule_id: number; rule_name: string; host: string }[] | null
    }
    vm.openWhitelist(sampleApp)
    await flushPromises()
    // 删掉 old.foo.io 触发服务端 409
    vm.removeHost(1)
    await vm.saveWhitelist()
    expect(vm.whitelistDialog).toBe(true) // 不关闭
    expect(vm.whitelistConflict).not.toBeNull()
    expect(vm.whitelistConflict).toHaveLength(1)
    expect(vm.whitelistConflict![0]).toMatchObject({
      rule_id: 42,
      rule_name: '强制升级规则',
      host: 'old.foo.io',
    })
  })
})
