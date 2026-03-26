<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { View, Download, SwitchButton } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { useLlmMode } from '@/composables/useLlmMode'
import type { CompareTask } from '@/types/compare'

// ── LLM 模式切换 ──────────────────────────────────────────
const { llmMock, loading: llmModeLoading, fetchLlmMode, toggleLlmMode } = useLlmMode()

const router = useRouter()
const auth = useAuthStore()

// ── 任务列表 ─────────────────────────────────────────────
const tasks = ref<CompareTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listLoading = ref(false)

async function fetchTasks() {
  listLoading.value = true
  try {
    const res = await request.get('/compare/tasks', {
      params: { page: page.value, page_size: pageSize.value },
    })
    tasks.value = res.data.items
    total.value = res.data.total
  } finally {
    listLoading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  fetchTasks()
}

// ── 导出报告 ─────────────────────────────────────────────
const exporting = ref<Record<string, boolean>>({})

async function exportReport(taskId: string, format: 'pdf' | 'docx') {
  const key = `${taskId}-${format}`
  exporting.value[key] = true
  try {
    const res = await request.post(`/reports/tasks/${taskId}/export`, null, {
      params: { format },
    })
    const a = document.createElement('a')
    a.href = res.data.download_url
    a.download = `比对报告.${format}`
    a.click()
    ElMessage.success('报告导出成功，即将下载')
  } finally {
    exporting.value[key] = false
  }
}

// ── 工具 ─────────────────────────────────────────────────
function statusTag(status: string): { type: 'success' | 'info' | 'warning' | 'danger'; label: string } {
  const map: Record<string, { type: 'success' | 'info' | 'warning' | 'danger'; label: string }> = {
    done:       { type: 'success', label: '已完成' },
    pending:    { type: 'info',    label: '等待中' },
    processing: { type: 'warning', label: '比对中' },
    failed:     { type: 'danger',  label: '失败' },
  }
  return map[status] ?? { type: 'info', label: status }
}

function formatDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(() => {
  fetchTasks()
  fetchLlmMode()
})
</script>

<template>
  <div class="report-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <span class="brand">莱钢集团 · AI 文档比对系统</span>
      <nav class="nav-links">
        <el-button text @click="router.push('/documents')">文档管理</el-button>
        <el-button text @click="router.push('/reports')">报告列表</el-button>
      </nav>
      <div class="nav-right">
        <span class="username">{{ auth.displayName }}</span>
        <el-button text :icon="SwitchButton" @click="handleLogout">退出</el-button>
      </div>
    </header>

    <main class="main-content">
      <div class="page-header">
        <span class="page-title">比对报告历史</span>
        <div class="page-header-actions">
          <el-tooltip :content="llmMock ? '当前：Mock 模式（点击切换为真实 LLM）' : '当前：真实 LLM 模式（点击切换为 Mock）'" placement="bottom">
            <el-button
              :type="llmMock ? 'warning' : 'success'"
              :loading="llmModeLoading"
              size="small"
              @click="toggleLlmMode"
            >
              {{ llmMock ? 'Mock 模式' : '真实 LLM' }}
            </el-button>
          </el-tooltip>
          <el-button @click="router.push('/documents')">返回文档管理</el-button>
        </div>
      </div>

      <!-- 任务表格 -->
      <el-table v-loading="listLoading" :data="tasks" stripe style="width: 100%">
        <el-table-column label="任务名称" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.task_name || row.task_id }}
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status).type">
              {{ statusTag(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="差异数" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.total_diffs !== null">{{ row.total_diffs }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="重大差异" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.critical_diffs" class="critical-count">{{ row.critical_diffs }}</span>
            <span v-else-if="row.status === 'done'" class="muted">0</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>

        <el-table-column label="完成时间" width="170">
          <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                text
                size="small"
                :icon="View"
                :disabled="row.status !== 'done'"
                @click="router.push(`/compare/${row.task_id}`)"
              >
                查看
              </el-button>
              <el-button
                text
                size="small"
                :icon="Download"
                :loading="exporting[`${row.task_id}-pdf`]"
                :disabled="row.status !== 'done'"
                @click="exportReport(row.task_id, 'pdf')"
              >
                PDF
              </el-button>
              <el-button
                text
                size="small"
                :icon="Download"
                :loading="exporting[`${row.task_id}-docx`]"
                :disabled="row.status !== 'done'"
                @click="exportReport(row.task_id, 'docx')"
              >
                Word
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="total > pageSize"
        class="pagination"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="onPageChange"
      />

      <!-- 空状态 -->
      <el-empty
        v-if="!listLoading && tasks.length === 0"
        description="暂无比对记录，前往文档管理页发起比对"
      >
        <el-button type="primary" @click="router.push('/documents')">去上传文档</el-button>
      </el-empty>
    </main>
  </div>
</template>

<style scoped>
.report-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

.top-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  position: sticky;
  top: 0;
  z-index: 100;
}

.brand {
  font-weight: 700;
  font-size: 16px;
  color: var(--el-color-primary);
  white-space: nowrap;
}

.nav-links { display: flex; gap: 4px; }

.nav-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.username {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.main-content {
  flex: 1;
  padding: 24px;
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.row-actions { display: flex; gap: 4px; }

.critical-count {
  color: var(--diff-risk-high, #d32f2f);
  font-weight: 600;
}

.muted { color: var(--el-text-color-placeholder); }

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
