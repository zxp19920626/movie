import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/shared/layout/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/shared/layout/LayoutView.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/modules/admin/views/DashboardPlaceholder.vue'),
        meta: { title: '数据看板' },
      },
      // cp 模块（App 分发平台）已实装
      {
        path: 'cp/apps',
        name: 'cp-apps',
        component: () => import('@/modules/channel-pack/views/AppsView.vue'),
        meta: { title: 'App 租户管理', permission: 'cp.view' },
      },
      {
        path: 'cp/channels',
        name: 'cp-channels',
        component: () => import('@/modules/channel-pack/views/ChannelsView.vue'),
        meta: { title: '渠道管理', permission: 'cp.view' },
      },
      {
        path: 'cp/versions',
        name: 'cp-versions',
        component: () => import('@/modules/channel-pack/views/VersionsView.vue'),
        meta: { title: '版本管理', permission: 'cp.view' },
      },
      {
        path: 'cp/rules',
        name: 'cp-rules',
        component: () => import('@/modules/channel-pack/views/RulesView.vue'),
        meta: { title: '升级规则', permission: 'cp.view' },
      },
      {
        path: 'cp/jobs',
        name: 'cp-jobs',
        component: () => import('@/modules/channel-pack/views/JobsView.vue'),
        meta: { title: '签名任务', permission: 'cp.view' },
      },
      // 其它模块占位（P3/P4 实装）
      {
        path: 'content/videos',
        name: 'content-videos',
        component: () => import('@/modules/content/views/VideosView.vue'),
        meta: { title: '影片管理', permission: 'content.view' },
      },
      {
        path: 'content/categories',
        name: 'content-categories',
        component: () => import('@/modules/content/views/CategoriesView.vue'),
        meta: { title: '分类管理', permission: 'content.view' },
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/modules/user/views/UsersView.vue'),
        meta: { title: '用户管理', permission: 'user.view' },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: () => import('@/modules/admin/views/Placeholder.vue'),
        meta: { title: '管理员', permission: 'permissions.view' },
      },
      {
        path: 'admin/roles',
        name: 'admin-roles',
        component: () => import('@/modules/admin/views/Placeholder.vue'),
        meta: { title: '角色权限', permission: 'permissions.view' },
      },
      {
        path: 'admin/logs',
        name: 'admin-logs',
        component: () => import('@/modules/admin/views/Placeholder.vue'),
        meta: { title: '操作日志', permission: 'permissions.view' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthed) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.isAuthed) {
    return { path: '/dashboard' }
  }
  const requiredPerm = to.meta.permission as string | undefined
  if (requiredPerm && !auth.hasPermission(requiredPerm)) {
    return { path: '/dashboard' }
  }
})

export default router
