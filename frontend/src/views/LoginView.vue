<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()

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
  <div :class="['login-page', themeStore.theme]">
    <!-- 深蓝科技主题背景装饰 -->
    <div v-if="themeStore.theme === 'tech'" class="tech-bg">
      <div class="tech-grid" />
      <div class="tech-glow tech-glow-1" />
      <div class="tech-glow tech-glow-2" />
    </div>

    <div class="login-wrap">
      <!-- Logo 区域 -->
      <div class="login-logo">
        <div class="logo-icon">
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
            <rect width="36" height="36" rx="8" fill="currentColor" fill-opacity="0.12"/>
            <path d="M8 18 L18 8 L28 18 L18 28 Z" stroke="currentColor" stroke-width="2" fill="none"/>
            <circle cx="18" cy="18" r="4" fill="currentColor"/>
          </svg>
        </div>
        <div class="logo-text">
          <span class="logo-main">莱钢集团</span>
          <span class="logo-sub">AI 文档比对系统</span>
        </div>
      </div>

      <!-- 登录卡片 -->
      <div class="login-card">
        <h2 class="card-title">欢迎回来</h2>
        <p class="card-desc">请使用您的账号登录系统</p>

        <el-form class="login-form" @submit.prevent="handleLogin" label-position="top">
          <el-form-item label="用户名">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              autocomplete="username"
              size="large"
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
              size="large"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-button
            type="primary"
            :loading="loading"
            class="login-btn"
            native-type="submit"
            size="large"
            @click="handleLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form>
      </div>

      <!-- 主题切换 -->
      <div class="theme-toggle-wrap">
        <button class="theme-toggle-btn" @click="themeStore.toggle()">
          <span v-if="themeStore.theme === 'tech'">☀ 切换为极简白风格</span>
          <span v-else>◈ 切换为深蓝科技风格</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 通用基础 ──────────────────────────────────────────────── */
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.login-wrap {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  width: 420px;
}

/* Logo */
.login-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-main {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
}

.logo-sub {
  font-size: 12px;
  opacity: 0.7;
}

/* 登录卡片 */
.login-card {
  width: 100%;
  padding: 36px 40px;
  border-radius: 12px;
  box-sizing: border-box;
}

.card-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
}

.card-desc {
  margin: 0 0 28px;
  font-size: 14px;
  opacity: 0.6;
}

.login-form {
  display: flex;
  flex-direction: column;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  font-size: 15px;
  letter-spacing: 2px;
  border-radius: 8px;
}

/* 主题切换按钮 */
.theme-toggle-wrap {
  text-align: center;
}

.theme-toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.2s, opacity 0.2s;
  opacity: 0.6;
}

.theme-toggle-btn:hover {
  opacity: 1;
}

/* ── 极简白主题 ───────────────────────────────────────────── */
.login-page.minimal {
  background: linear-gradient(145deg, var(--login-bg-start), var(--login-bg-end));
}

.login-page.minimal .login-logo {
  color: #2563eb;
}

.login-page.minimal .logo-main {
  color: #111827;
}

.login-page.minimal .logo-sub {
  color: #6b7280;
}

.login-page.minimal .login-card {
  background: var(--login-card-bg);
  border: 1px solid var(--login-card-border);
  box-shadow: var(--login-card-shadow);
}

.login-page.minimal .card-title {
  color: #111827;
}

.login-page.minimal .card-desc {
  color: #6b7280;
}

.login-page.minimal .theme-toggle-btn {
  color: #2563eb;
}

.login-page.minimal .theme-toggle-btn:hover {
  background: rgba(37, 99, 235, 0.06);
}

.login-page.minimal :deep(.el-form-item__label) {
  color: #374151;
  font-weight: 500;
}

/* ── 深蓝科技主题 ─────────────────────────────────────────── */
.login-page.tech {
  background: linear-gradient(135deg, var(--login-bg-start) 0%, var(--login-bg-end) 100%);
}

/* 网格背景 */
.tech-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.tech-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(79, 142, 247, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(79, 142, 247, 0.06) 1px, transparent 1px);
  background-size: 40px 40px;
}

.tech-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
}

.tech-glow-1 {
  width: 400px;
  height: 400px;
  top: -100px;
  right: -80px;
  background: radial-gradient(circle, #1d4ed8, transparent 70%);
}

.tech-glow-2 {
  width: 300px;
  height: 300px;
  bottom: -80px;
  left: -60px;
  background: radial-gradient(circle, #0ea5e9, transparent 70%);
}

.login-page.tech .login-logo {
  color: #60a5fa;
}

.login-page.tech .logo-main {
  color: #ffffff;
}

.login-page.tech .logo-sub {
  color: rgba(255, 255, 255, 0.6);
}

.login-page.tech .login-card {
  background: var(--login-card-bg);
  border: 1px solid var(--login-card-border);
  box-shadow: var(--login-card-shadow);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.login-page.tech .card-title {
  color: #ffffff;
}

.login-page.tech .card-desc {
  color: rgba(255, 255, 255, 0.55);
}

.login-page.tech .theme-toggle-btn {
  color: rgba(255, 255, 255, 0.55);
}

.login-page.tech .theme-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.9);
}

/* 深蓝主题 Element Plus 输入框覆盖 */
.login-page.tech :deep(.el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.07);
  box-shadow: 0 0 0 1px rgba(79, 142, 247, 0.35) inset;
}

.login-page.tech :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(79, 142, 247, 0.65) inset;
}

.login-page.tech :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #4f8ef7 inset;
}

.login-page.tech :deep(.el-input__inner) {
  color: rgba(255, 255, 255, 0.9);
}

.login-page.tech :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.3);
}

.login-page.tech :deep(.el-input__prefix-inner .el-icon) {
  color: rgba(255, 255, 255, 0.45);
}

.login-page.tech :deep(.el-input__suffix .el-icon) {
  color: rgba(255, 255, 255, 0.45);
}

.login-page.tech :deep(.el-form-item__label) {
  color: rgba(255, 255, 255, 0.75);
  font-weight: 500;
}

.login-page.tech :deep(.el-button--primary) {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border-color: transparent;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45);
}

.login-page.tech :deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  box-shadow: 0 4px 20px rgba(37, 99, 235, 0.6);
}
</style>
