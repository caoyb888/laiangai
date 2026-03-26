<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import request from '@/api/request'

// 允许类型，见 CLAUDE.md §6.3
const ALLOWED_TYPES = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'application/pdf',
  'text/plain',
]
const ALLOWED_EXT = ['.docx', '.doc', '.pdf', '.txt']
const MAX_SIZE_MB = 200

const props = defineProps<{
  category?: string
}>()

const emit = defineEmits<{
  uploaded: [docId: string, fileName: string]
}>()

const uploading = ref(false)
const uploadProgress = ref(0)
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

function openFilePicker() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  // 清空 input，允许重复选同一文件（在取出 file 后再清空）
  input.value = ''
  if (file) doUpload(file)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) doUpload(file)
}

async function doUpload(file: File) {
  // 类型校验：先用 MIME，再用扩展名兜底
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXT.includes(ext)) {
    ElMessage.error('仅支持 Word（.docx/.doc）、PDF、TXT 格式文件')
    return
  }
  if (file.size / 1024 / 1024 > MAX_SIZE_MB) {
    ElMessage.error(`文件不能超过 ${MAX_SIZE_MB}MB`)
    return
  }

  uploading.value = true
  uploadProgress.value = 0

  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', props.category || 'other')

  try {
    const res = await request.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        uploadProgress.value = Math.round((e.loaded * 90) / (e.total || 1))
      },
    })
    uploadProgress.value = 100
    ElMessage.success('上传成功，正在解析中...')
    emit('uploaded', res.data.document_id, res.data.file_name)
  } catch (err: unknown) {
    uploadProgress.value = 0
    const msg = err instanceof Error ? err.message : '请重试'
    ElMessage({ type: 'error', message: msg, duration: 5000, showClose: true })
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="doc-uploader">
    <!-- 隐藏的原生 input -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".docx,.doc,.pdf,.txt"
      style="display: none"
      @change="onFileChange"
    />

    <!-- 拖拽 / 点击区域 -->
    <div
      class="drop-zone"
      :class="{ 'is-dragging': isDragging, 'is-uploading': uploading }"
      @click="openFilePicker"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <el-icon class="upload-icon" :size="48"><UploadFilled /></el-icon>
      <p class="upload-text">
        <span v-if="uploading">上传中，请稍候...</span>
        <span v-else>拖拽文件至此，或 <em>点击选择文件</em></span>
      </p>
      <p class="upload-tip">支持 Word (.docx/.doc)、PDF、TXT，单文件不超过 {{ MAX_SIZE_MB }}MB</p>
    </div>

    <!-- 进度条 -->
    <el-progress
      v-if="uploading"
      :percentage="uploadProgress"
      :striped="true"
      :striped-flow="true"
      style="margin-top: 12px"
    />
  </div>
</template>

<style scoped>
.drop-zone {
  border: 2px dashed var(--el-border-color);
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  user-select: none;
}

.drop-zone:hover,
.drop-zone.is-dragging {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.drop-zone.is-uploading {
  cursor: not-allowed;
  opacity: 0.7;
}

.upload-icon {
  color: var(--el-color-primary);
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  margin: 0 0 6px;
}

.upload-text em {
  color: var(--el-color-primary);
  font-style: normal;
}

.upload-tip {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin: 0;
}
</style>
