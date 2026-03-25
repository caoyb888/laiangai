import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,  // 60秒，比对任务可能较慢
})

// 请求拦截器：注入 Token（见 CLAUDE.md §6.4，禁止在业务代码中手动添加 Authorization 头）
request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器：统一错误处理（见 CLAUDE.md §6.4）
request.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    if (data.code && data.code !== 200) {
      // 认证失效
      if (data.code === 4100 || data.code === 4102) {
        useAuthStore().logout()
        router.push('/login')
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
      ElMessage.error(data.message || '操作失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    const msg = error.response?.data?.message || error.message || '网络异常'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
