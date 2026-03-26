<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, DocumentCopy, SwitchButton } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import DocumentUploader from '@/components/common/DocumentUploader.vue'

const router = useRouter()
const auth = useAuthStore()

// ── 文档列表 ────────────────────────────────────────────
interface DocItem {
  document_id: string
  file_name: string
  file_type: string
  parse_status: string
  category: string
  title: string | null
  created_at: string
}

const docs = ref<DocItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const listLoading = ref(false)

async function fetchDocs() {
  listLoading.value = true
  try {
    const res = await request.get('/documents/', {
      params: { page: page.value, page_size: pageSize.value },
    })
    docs.value = res.data.items
    total.value = res.data.total
  } finally {
    listLoading.value = false
  }
}

function onPageChange(p: number) {
  page.value = p
  fetchDocs()
}

// ── 上传 ────────────────────────────────────────────────
const showUpload = ref(false)

function onUploadSuccess(_docId: string, _fileName: string) {
  showUpload.value = false
  fetchDocs()
}

// ── 删除 ────────────────────────────────────────────────
async function handleDelete(doc: DocItem) {
  await ElMessageBox.confirm(
    `确认删除「${doc.file_name}」？删除后不可恢复。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  await request.delete(`/documents/${doc.document_id}`)
  ElMessage.success('已删除')
  fetchDocs()
}

// ── 比对选择 ─────────────────────────────────────────────
const selected = ref<DocItem[]>([])

function toggleSelect(doc: DocItem) {
  const idx = selected.value.findIndex(d => d.document_id === doc.document_id)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
  } else {
    if (selected.value.length >= 2) {
      ElMessage.warning('最多选择 2 份文档进行比对')
      return
    }
    if (doc.parse_status !== 'done') {
      ElMessage.warning('请选择已解析完成的文档')
      return
    }
    selected.value.push(doc)
  }
}

function isSelected(doc: DocItem) {
  return selected.value.some(d => d.document_id === doc.document_id)
}

// ── 发起比对 ─────────────────────────────────────────────
const comparing = ref(false)

async function startCompare() {
  if (selected.value.length !== 2) {
    ElMessage.warning('请选择 2 份文档')
    return
  }
  comparing.value = true
  try {
    const res = await request.post('/compare/tasks', {
      doc_a_id: selected.value[0].document_id,
      doc_b_id: selected.value[1].document_id,
      task_name: `${selected.value[0].file_name} vs ${selected.value[1].file_name}`,
    })
    ElMessage.success('比对任务已创建')
    router.push(`/compare/${res.data.task_id}`)
  } finally {
    comparing.value = false
  }
}

// ── 工具函数 ──────────────────────────────────────────────
function statusTag(status: string): { type: 'success' | 'info' | 'warning' | 'danger'; label: string } {
  const map: Record<string, { type: 'success' | 'info' | 'warning' | 'danger'; label: string }> = {
    done:       { type: 'success', label: '已解析' },
    pending:    { type: 'info',    label: '待解析' },
    processing: { type: 'warning', label: '解析中' },
    failed:     { type: 'danger',  label: '解析失败' },
  }
  return map[status] ?? { type: 'info', label: status }
}

function fileTypeLabel(t: string) {
  return t?.toUpperCase() ?? '-'
}

function formatDate(iso: string) {
  return iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(fetchDocs)
</script>

<template>
  <div class="doc-page">
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
      <!-- 操作栏 -->
      <div class="action-bar">
        <div class="action-left">
          <el-button type="primary" :icon="UploadFilled" @click="showUpload = !showUpload">
            上传文档
          </el-button>
          <el-button
            type="success"
            :icon="DocumentCopy"
            :disabled="selected.length !== 2"
            :loading="comparing"
            @click="startCompare"
          >
            开始比对
            <span v-if="selected.length > 0">（已选 {{ selected.length }}/2）</span>
          </el-button>
          <el-button v-if="selected.length > 0" text @click="selected = []">
            清除选择
          </el-button>
        </div>
        <span class="total-hint">共 {{ total }} 份文档</span>
      </div>

      <!-- 上传区（折叠） -->
      <el-collapse-transition>
        <el-card v-if="showUpload" class="upload-card" shadow="never">
          <DocumentUploader category="other" @uploaded="onUploadSuccess" />
        </el-card>
      </el-collapse-transition>

      <!-- 已选提示 -->
      <el-alert
        v-if="selected.length > 0"
        :title="`已选：${selected.map(d => d.file_name).join(' vs ')}`"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />

      <!-- 文档表格 -->
      <el-table
        v-loading="listLoading"
        :data="docs"
        stripe
        style="width: 100%"
        @row-click="toggleSelect"
      >
        <el-table-column width="48">
          <template #default="{ row }">
            <el-checkbox :model-value="isSelected(row)" @click.stop="toggleSelect(row)" />
          </template>
        </el-table-column>

        <el-table-column label="文件名" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'selected-row-name': isSelected(row) }">
              {{ row.file_name }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ fileTypeLabel(row.file_type) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="解析状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.parse_status).type">
              {{ statusTag(row.parse_status).label }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="category" label="分类" width="100" show-overflow-tooltip />

        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="danger"
              :icon="Delete"
              size="small"
              @click.stop="handleDelete(row)"
            />
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
        v-if="!listLoading && docs.length === 0"
        description="暂无文档，点击「上传文档」开始使用"
      />
    </main>
  </div>
</template>

<style scoped>
.doc-page {
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

.nav-links {
  display: flex;
  gap: 4px;
}

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

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.action-left {
  display: flex;
  gap: 8px;
  align-items: center;
}

.total-hint {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

.upload-card {
  margin-bottom: 16px;
  border: 1px dashed var(--el-border-color);
}

.selected-row-name {
  color: var(--el-color-primary);
  font-weight: 500;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
