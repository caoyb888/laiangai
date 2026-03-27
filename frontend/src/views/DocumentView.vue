<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete, DocumentCopy, SwitchButton } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useLlmMode } from '@/composables/useLlmMode'
import DocumentUploader from '@/components/common/DocumentUploader.vue'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'

const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()
const { llmMock, loading: llmModeLoading, fetchLlmMode, toggleLlmMode } = useLlmMode()

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
  } catch (err: unknown) {
    const msg = (err as Error).message || '获取文档列表失败，请检查服务是否正常'
    ElMessage.error(msg)
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
const baseDocId = ref<string | null>(null)

function toggleSelect(doc: DocItem) {
  const idx = selected.value.findIndex(d => d.document_id === doc.document_id)
  if (idx >= 0) {
    selected.value.splice(idx, 1)
    if (baseDocId.value === doc.document_id) {
      baseDocId.value = selected.value.length > 0 ? selected.value[0].document_id : null
    }
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
    if (baseDocId.value === null) {
      baseDocId.value = doc.document_id
    }
  }
}

function isSelected(doc: DocItem) {
  return selected.value.some(d => d.document_id === doc.document_id)
}

function docRole(doc: DocItem): 'base' | 'compare' | null {
  if (!isSelected(doc)) return null
  return doc.document_id === baseDocId.value ? 'base' : 'compare'
}

function setBase(doc: DocItem) {
  baseDocId.value = doc.document_id
}

// ── 发起比对 ─────────────────────────────────────────────
const comparing = ref(false)

async function startCompare() {
  if (selected.value.length !== 2) {
    ElMessage.warning('请选择 2 份文档')
    return
  }
  const base = selected.value.find(d => d.document_id === baseDocId.value)!
  const compare = selected.value.find(d => d.document_id !== baseDocId.value)!
  comparing.value = true
  try {
    const res = await request.post('/compare/tasks', {
      doc_a_id: base.document_id,
      doc_b_id: compare.document_id,
      task_name: `${base.file_name} vs ${compare.file_name}`,
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

onMounted(() => {
  fetchDocs()
  fetchLlmMode()
})
</script>

<template>
  <div :class="['doc-page', themeStore.theme]">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <span class="brand">莱钢集团 · AI 文档比对系统</span>
      <nav class="nav-links">
        <el-button text @click="router.push('/documents')">文档管理</el-button>
        <el-button text @click="router.push('/reports')">报告列表</el-button>
      </nav>
      <div class="nav-right">
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
        <ThemeSwitcher />
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
        :title="selected.length === 2
          ? `基准：${selected.find(d => d.document_id === baseDocId)?.file_name}　对比：${selected.find(d => d.document_id !== baseDocId)?.file_name}`
          : `已选：${selected[0].file_name}（将作为基准文档）`"
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

        <el-table-column label="操作" width="80">
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

        <el-table-column label="角色" width="90" fixed="right">
          <template #default="{ row }">
            <template v-if="docRole(row) === 'base'">
              <el-tag size="small" type="primary" effect="dark">基准文档</el-tag>
            </template>
            <template v-else-if="docRole(row) === 'compare'">
              <el-tag
                size="small"
                type="info"
                effect="plain"
                style="cursor:pointer"
                @click.stop="setBase(row)"
              >对比文档</el-tag>
            </template>
            <template v-else>
              <span class="role-hint">基准/对比</span>
            </template>
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
  background: var(--page-bg);
  display: flex;
  flex-direction: column;
}

.top-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  height: 56px;
  background: var(--nav-bg);
  border-bottom: 1px solid var(--nav-border);
  position: sticky;
  top: 0;
  z-index: 100;
  transition: background 0.25s, border-color 0.25s;
}

.brand {
  font-weight: 700;
  font-size: 16px;
  color: var(--nav-brand-color);
  white-space: nowrap;
  transition: color 0.25s;
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
  color: var(--nav-text-secondary);
  transition: color 0.25s;
}

/* ── 深蓝科技主题覆盖 ─────────────────────────────────────── */
.doc-page.tech .top-nav :deep(.el-button--text),
.doc-page.tech .top-nav :deep(.el-button.is-text) {
  color: var(--nav-text);
}

.doc-page.tech .top-nav :deep(.el-button--text:hover),
.doc-page.tech .top-nav :deep(.el-button.is-text:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.doc-page.tech .main-content :deep(.el-card) {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(79, 142, 247, 0.2);
}

.doc-page.tech .main-content :deep(.el-table) {
  background: transparent;
  color: var(--nav-text);
}

/* 表头 */
.doc-page.tech .main-content :deep(.el-table th.el-table__cell) {
  background: rgba(79, 142, 247, 0.18);
  color: #ffffff !important;
  border-bottom-color: rgba(79, 142, 247, 0.25);
}

/* 普通行 */
.doc-page.tech .main-content :deep(.el-table td.el-table__cell) {
  background: rgba(13, 31, 60, 0.85);
  color: rgba(255, 255, 255, 0.82);
  border-bottom-color: rgba(79, 142, 247, 0.12);
}

/* 斑马纹奇数行 */
.doc-page.tech .main-content :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(79, 142, 247, 0.1);
  color: rgba(255, 255, 255, 0.82) !important;
}

/* hover 行 */
.doc-page.tech .main-content :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(79, 142, 247, 0.18) !important;
}

/* 表头单元格内所有文字 */
.doc-page.tech .main-content :deep(.el-table th.el-table__cell .cell) {
  color: #ffffff !important;
}

/* 斑马纹行单元格内所有文字 */
.doc-page.tech .main-content :deep(.el-table--striped .el-table__row--striped td.el-table__cell .cell) {
  color: rgba(255, 255, 255, 0.82) !important;
}

/* 表格整体包裹层 & 分割线 */
.doc-page.tech .main-content :deep(.el-table__inner-wrapper::before) {
  background: rgba(79, 142, 247, 0.2);
}

/* 固定列阴影区域 */
.doc-page.tech .main-content :deep(.el-table__body-wrapper) {
  background: transparent;
}

.doc-page.tech .total-hint {
  color: var(--nav-text-secondary);
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

.role-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
