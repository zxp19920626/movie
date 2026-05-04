<script setup lang="ts">
// 搬自 nextstream/admin/src/views/LoginView.vue，做了如下改动：
//   - 文案从 NextStream 改为 Movie
//   - 去掉演示账号提示（生产用）
//   - role 校验从 'ADMIN' 改为新 RBAC：是否能登后台由后端 a_admin_users.status 决定，前端不做白名单
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/shared/stores/auth'
import { ElMessage } from 'element-plus'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('')
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!email.value || !password.value) {
    ElMessage.warning('请输入邮箱和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">MV</div>
        <div>
          <h1>Movie Admin</h1>
          <p>多租户 App 分发平台 · 管理后台</p>
        </div>
      </div>
      <el-form @submit.prevent="onSubmit" label-position="top" size="large">
        <el-form-item label="邮箱">
          <el-input v-model="email" type="email" placeholder="admin@your-domain.com" autofocus />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password placeholder="••••••••" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">登录</el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 20% 20%, rgba(45, 108, 223, 0.18), transparent 40%),
    radial-gradient(circle at 80% 80%, rgba(45, 108, 223, 0.10), transparent 50%),
    #1a1d27;
}
.login-card {
  width: 420px;
  background: #252834;
  border: 1px solid #3a3f51;
  border-radius: 8px;
  padding: 32px;
  color: #eee;
  box-shadow: 0 20px 60px rgba(0,0,0,0.4);
}
.login-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}
.logo {
  width: 44px; height: 44px;
  border-radius: 10px;
  background: var(--mv-primary);
  color: white;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700;
  font-size: 16px;
}
.login-header h1 {
  margin: 0;
  font-size: 18px;
  color: #fff;
}
.login-header p {
  margin: 2px 0 0;
  font-size: 12px;
  color: #909399;
}
.login-card :deep(.el-form-item__label) {
  color: #abb1bf;
}
.login-card :deep(.el-input__wrapper) {
  background: #2a2e3d;
  box-shadow: 0 0 0 1px #3a3f51 inset;
}
.login-card :deep(.el-input__inner) {
  color: #fff;
}
</style>
