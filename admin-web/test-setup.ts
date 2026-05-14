// 全局 mock / 测试 setup
import { config } from '@vue/test-utils'
import { vi } from 'vitest'

// jsdom opaque origin 默认拒 localStorage；测试中用一份内存实现
if (typeof window !== 'undefined') {
  const memStore = new Map<string, string>()
  const ls = {
    getItem: (k: string) => (memStore.has(k) ? memStore.get(k)! : null),
    setItem: (k: string, v: string) => { memStore.set(k, String(v)) },
    removeItem: (k: string) => { memStore.delete(k) },
    clear: () => { memStore.clear() },
    key: (i: number) => Array.from(memStore.keys())[i] ?? null,
    get length() { return memStore.size },
  }
  Object.defineProperty(window, 'localStorage', { value: ls, configurable: true })
  Object.defineProperty(globalThis, 'localStorage', { value: ls, configurable: true })
}

// element-plus 组件在 jsdom 环境会因 CSS 导入失败而崩溃。
// 在测试里我们不验证视觉/样式，对所有 el-* 组件做透明 stub（render slot）。
config.global.stubs = {
  ...(config.global.stubs as Record<string, unknown>),
}

// 只覆盖 ElMessage / ElMessageBox（在测试中不希望真的弹），其它组件保留 element-plus 原实现
vi.mock('element-plus', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  const noop = vi.fn()
  return {
    ...actual,
    ElMessage: { success: noop, error: noop, warning: noop, info: noop },
    ElMessageBox: { confirm: vi.fn(() => Promise.resolve()) },
  }
})
