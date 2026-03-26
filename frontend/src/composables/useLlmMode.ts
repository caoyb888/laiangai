import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const llmMock = ref(false)
const loading = ref(false)
let initialized = false

export function useLlmMode() {
  async function fetchLlmMode() {
    if (initialized) return
    try {
      const res = await request.get('/settings/llm-mode')
      llmMock.value = res.data.mock
      initialized = true
    } catch {
      // 静默失败，不影响页面渲染
    }
  }

  async function toggleLlmMode() {
    loading.value = true
    try {
      const res = await request.post('/settings/llm-mode', null, {
        params: { mock: !llmMock.value },
      })
      llmMock.value = res.data.mock
      ElMessage.success(`已切换到 ${llmMock.value ? 'Mock 模式' : '真实 LLM 模式'}`)
    } catch {
      ElMessage.error('切换失败')
    } finally {
      loading.value = false
    }
  }

  return { llmMock, loading, fetchLlmMode, toggleLlmMode }
}
