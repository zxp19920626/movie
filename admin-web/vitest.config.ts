import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(viteConfig, defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test-setup.ts'],
    server: {
      deps: {
        // element-plus 通过 unplugin-vue-components 自动注入 import 'element-plus/es/components/.../style/css'
        // 不 inline 时 Node ESM loader 直接试图加载 .css 文件失败。inline 后由 vite 处理。
        inline: ['element-plus'],
      },
    },
  },
}))
