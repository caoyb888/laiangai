<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import DiffPanel from '@/components/compare/DiffPanel.vue'
import DiffNavigator from '@/components/compare/DiffNavigator.vue'
import request from '@/api/request'
import type { DiffItem, CompareTask } from '@/types/compare'

const route = useRoute()
const taskId = route.params.taskId as string

const task = ref<CompareTask | null>(null)
const diffItems = ref<DiffItem[]>([])
const currentIndex = ref(0)
const loading = ref(true)
const failed = ref(false)
const exporting = ref(false)
const diffPanelRef = ref<InstanceType<typeof DiffPanel> | null>(null)

// 轮询任务状态
let pollTimer: ReturnType<typeof setInterval> | null = null

async function loadTask() {
  try {
    const res = await request.get(`/compare/tasks/${taskId}`)
    task.value = res.data
    if (res.data.status === 'done') {
      await loadDiffs()
      stopPolling()
      loading.value = false
    } else if (res.data.status === 'failed') {
      failed.value = true
      stopPolling()
      loading.value = false
    }
  } catch {
    // 轮询期间的偶发网络/服务端错误静默忽略，下次轮询自动重试
  }
}

async function loadDiffs() {
  const res = await request.get(`/compare/tasks/${taskId}/diffs`, {
    params: { page: 1, page_size: 9999 }
  })
  diffItems.value = res.data.items
}

function startPolling() {
  pollTimer = setInterval(loadTask, 3000)
}
function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
}

async function exportReport(format: 'pdf' | 'docx') {
  exporting.value = true
  try {
    // Step 1: 生成报告，获取下载路径
    const res = await request.post(`/reports/tasks/${taskId}/export`, null, {
      params: { format }
    })
    const downloadPath = res.data.download_url  // 形如 /api/v1/reports/download/{id}

    // Step 2: 用 axios（带 token）以 blob 方式下载文件
    const blobRes = await request.get(downloadPath, { responseType: 'blob' })
    const url = URL.createObjectURL(blobRes.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `比对报告_${taskId}.${format}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('报告导出成功')
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  loadTask()
  startPolling()
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="compare-view">
    <!-- 顶部状态栏 -->
    <div class="compare-topbar">
      <div class="task-info">
        <span>{{ task?.task_name || '比对任务' }}</span>
        <el-tag v-if="task?.status === 'processing'" type="warning">
          处理中 {{ task.progress }}%
        </el-tag>
        <el-tag v-else-if="task?.status === 'done'" type="success">
          完成｜共 {{ task.total_diffs }} 处差异
          <span v-if="task.critical_diffs" style="color: var(--diff-risk-critical)">
            ，{{ task.critical_diffs }} 处重大
          </span>
        </el-tag>
      </div>
      <div class="export-actions">
        <el-button
          size="small" :loading="exporting"
          @click="exportReport('pdf')"
        >导出 PDF</el-button>
        <el-button
          size="small" :loading="exporting"
          @click="exportReport('docx')"
        >导出 Word</el-button>
      </div>
    </div>

    <!-- 主体：比对面板 + 导航条 -->
    <div v-if="loading" class="loading-state">
      <el-progress
        type="circle"
        :percentage="task?.progress || 0"
      />
      <p>正在比对中，请稍候...</p>
    </div>

    <div v-else-if="failed" class="loading-state">
      <el-result
        icon="error"
        title="比对任务失败"
        :sub-title="task?.error_msg || '请重新发起比对'"
      >
        <template #extra>
          <el-button type="primary" @click="$router.push('/documents')">返回文档管理</el-button>
        </template>
      </el-result>
    </div>

    <div v-else class="compare-body">
      <DiffPanel
        ref="diffPanelRef"
        :diff-items="diffItems"
        :doc-a-name="task?.doc_a_name || '文档A'"
        :doc-b-name="task?.doc_b_name || '文档B'"
      />
      <DiffNavigator
        :items="diffItems"
        :current-index="currentIndex"
        @jump-to="(i) => { currentIndex = i; diffPanelRef?.jumpTo(i) }"
      />
    </div>
  </div>
</template>

<style scoped>
.compare-view { display: flex; flex-direction: column; height: 100vh; }
.compare-topbar {
  height: var(--header-height); display: flex; align-items: center;
  justify-content: space-between; padding: 0 16px;
  border-bottom: 1px solid #dcdfe6; background: #fff; flex-shrink: 0;
}
.task-info { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; }
.export-actions { display: flex; gap: 8px; }
.compare-body { flex: 1; display: flex; overflow: hidden; }
.loading-state { flex: 1; display: flex; flex-direction: column;
                 align-items: center; justify-content: center; gap: 16px; }
</style>
