import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>('')
  const userId = ref<string>('')
  const displayName = ref<string>('')
  const role = ref<string>('viewer')

  function setAuth(data: {
    access_token: string; user_id: string
    display_name: string; role: string
  }) {
    token.value = data.access_token
    userId.value = data.user_id
    displayName.value = data.display_name
    role.value = data.role
    // 注意：不存入 localStorage，见 CLAUDE.md §11（禁止前端存储文档内容到 localStorage/sessionStorage）
    // token 临时存入 sessionStorage 用于页面刷新恢复，tab 关闭即清除
    sessionStorage.setItem('auth_token', data.access_token)
  }

  function logout() {
    token.value = ''
    userId.value = ''
    displayName.value = ''
    role.value = 'viewer'
    sessionStorage.removeItem('auth_token')
  }

  function restoreFromSession() {
    const t = sessionStorage.getItem('auth_token')
    if (t) token.value = t
  }

  return { token, userId, displayName, role, setAuth, logout, restoreFromSession }
})
