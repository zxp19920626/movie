<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'
import { useCpStore } from '@/modules/channel-pack/stores/cp'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const cpStore = useCpStore()

interface NavItem {
  name: string
  label: string
  icon: string
  permission?: string
}

const navItems: NavItem[] = [
  { name: 'dashboard',    label: '数据看板',     icon: 'Odometer',    permission: 'dashboard.view' },
  { name: 'cp-apps',      label: 'App 租户',     icon: 'Box',         permission: 'cp.view' },
  { name: 'cp-channels',  label: '渠道管理',     icon: 'Connection',  permission: 'cp.view' },
  { name: 'cp-versions',  label: '版本管理',     icon: 'Upload',      permission: 'cp.view' },
  { name: 'cp-rules',     label: '升级规则',     icon: 'Promotion',   permission: 'cp.view' },
  { name: 'cp-jobs',      label: '签名任务',     icon: 'List',        permission: 'cp.view' },
  { name: 'content-videos',     label: '影片管理',  icon: 'VideoCamera', permission: 'content.view' },
  { name: 'content-categories', label: '分类管理',  icon: 'Menu',        permission: 'content.view' },
  { name: 'users',        label: '用户管理',     icon: 'User',        permission: 'user.view' },
  { name: 'admin-users',     label: '管理员',     icon: 'Avatar',  permission: 'permissions.view' },
  { name: 'admin-roles',     label: '角色权限',   icon: 'Lock',    permission: 'permissions.view' },
  { name: 'admin-logs',      label: '操作日志',   icon: 'Document', permission: 'permissions.view' },
]

const visibleNav = computed(() =>
  navItems.filter((it) => !it.permission || auth.hasPermission(it.permission))
)
const activeName = computed(() => route.name as string)

function onSelect(name: string) {
  router.push({ name })
}

function onLogout() {
  auth.logout()
  router.replace('/login')
}

const userInitials = computed(() => {
  const n = auth.user?.display_name || auth.user?.email || 'MV'
  return n.replace(/[^a-zA-Z一-龥]/g, '').slice(0, 2).toUpperCase() || 'MV'
})

function onAppChange(id: number) {
  cpStore.setCurrentApp(id)
}

onMounted(() => {
  if (auth.isAuthed && cpStore.apps.length === 0) {
    cpStore.refreshApps().catch(() => {})
  }
})
</script>

<template>
  <el-container class="layout">
    <el-header class="layout-header">
      <div class="brand">
        <span class="brand-logo">MV</span>
        <span class="brand-title">Movie Admin</span>
        <span class="brand-tag">App 分发平台</span>
      </div>
      <div class="header-right">
        <span class="app-selector-label">当前 App：</span>
        <el-select
          :model-value="cpStore.currentAppId"
          @change="onAppChange"
          placeholder="未选择"
          size="small"
          style="width: 200px"
          clearable
        >
          <el-option v-for="app in cpStore.apps" :key="app.id" :label="`${app.name} (${app.package_name})`" :value="app.id" />
        </el-select>
        <el-dropdown @command="(c: string) => c === 'logout' && onLogout()">
          <span class="user">
            <span class="avatar">{{ userInitials }}</span>
            <span class="user-name">{{ auth.user?.display_name || auth.user?.email }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>{{ auth.user?.email }}</el-dropdown-item>
              <el-dropdown-item disabled>角色：{{ auth.user?.role }}</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>
    <el-container>
      <el-aside width="220px" class="layout-aside">
        <el-menu
          :default-active="activeName"
          background-color="#252834"
          text-color="#abb1bf"
          active-text-color="#ffffff"
          @select="onSelect"
        >
          <el-menu-item v-for="item in visibleNav" :key="item.name" :index="item.name">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
        <div class="aside-foot">
          租户数：<span style="color: #67C23A">{{ cpStore.apps.length }}</span><br />
          版本：v0.2.0-mvp
        </div>
      </el-aside>
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <component :is="Component" />
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout { height: 100vh; }
.layout-header {
  background: var(--mv-dark);
  color: white;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; height: 48px !important;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-logo {
  width: 24px; height: 24px; border-radius: 4px;
  background: var(--mv-primary);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
}
.brand-title { font-weight: 700; font-size: 14px; }
.brand-tag { font-size: 11px; opacity: 0.5; margin-left: 8px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.app-selector-label { font-size: 12px; color: #abb1bf; }
.user {
  display: flex; align-items: center; gap: 8px;
  cursor: pointer; color: white; outline: none;
}
.avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--mv-primary);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
}
.user-name { font-size: 13px; }
.layout-aside {
  background: var(--mv-dark);
  display: flex; flex-direction: column;
}
.layout-aside .el-menu { flex: 1; border-right: none; }
.layout-aside :deep(.el-menu-item.is-active) { background: var(--mv-primary) !important; }
.aside-foot {
  padding: 12px 16px;
  background: #1e222d;
  font-size: 10px;
  color: #6b7280;
  line-height: 1.6;
}
.layout-main {
  background: var(--mv-bg);
  padding: 24px;
  overflow-y: auto;
}
</style>
