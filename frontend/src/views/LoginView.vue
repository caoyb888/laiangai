<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    // OAuth2PasswordRequestForm 要求 application/x-www-form-urlencoded
    const params = new URLSearchParams()
    params.append('username', form.username)
    params.append('password', form.password)
    const res = await axios.post('/api/v1/auth/login', params)
    const data = res.data?.data ?? res.data
    auth.setAuth({
      access_token: data.access_token,
      user_id: data.user_id,
      display_name: data.display_name,
      role: data.role,
    })
    ElMessage.success(`欢迎，${data.display_name}`)
    router.push('/documents')
  } catch (err: unknown) {
    const msg =
      (err as { response?: { data?: { detail?: string; message?: string } } })
        ?.response?.data?.detail ??
      (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ??
      '登录失败，请检查用户名或密码'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <template #header>
        <div class="card-header">
          <span class="system-title">莱钢集团</span>
          <span class="system-subtitle">AI 文档比对系统</span>
        </div>
      </template>

      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            autocomplete="username"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-button
          type="primary"
          :loading="loading"
          class="login-btn"
          native-type="submit"
          @click="handleLogin"
        >
          {{ loading ? '登录中...' : '登 录' }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}

.login-card {
  width: 380px;
}

.card-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.system-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-color-primary);
}

.system-subtitle {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.login-btn {
  width: 100%;
  margin-top: 8px;
}
</style>
