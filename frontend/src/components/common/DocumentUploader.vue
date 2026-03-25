<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRawFile } from 'element-plus'
import request from '@/api/request'

// 允许类型，见 CLAUDE.md §6.3
const ALLOWED_TYPES = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/msword',
  'application/pdf',
  'text/plain',
]
const MAX_SIZE_MB = 200

const props = defineProps<{
  category?: string
  onSuccess?: (docId: string, fileName: string) => void
}>()

const uploading = ref(false)
const uploadProgress = ref(0)

function beforeUpload(rawFile: UploadRawFile): boolean {
  if (!ALLOWED_TYPES.includes(rawFile.type)) {
    ElMessage.error('仅支持 Word、PDF、TXT 格式文件')
    return false
  }
  if (rawFile.size / 1024 / 1024 > MAX_SIZE_MB) {
    ElMessage.error(`文件不能超过 ${MAX_SIZE_MB}MB`)
    return false
  }
  return true
}

async function handleUpload(options: { file: File }): Promise<void> {
  uploading.value = true
  uploadProgress.value = 0

  const formData = new FormData()
  formData.append('file', options.file)
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
    props.onSuccess?.(res.data.document_id, res.data.file_name)
  } catch {
    uploadProgress.value = 0
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="doc-uploader">
    <el-upload
      drag
      :http-request="handleUpload"
      :before-upload="beforeUpload"
      :show-file-list="false"
      accept=".docx,.doc,.pdf,.txt"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件至此，或 <em>点击上传</em>
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持 Word (.docx/.doc)、PDF、TXT，单文件不超过 {{ MAX_SIZE_MB }}MB
        </div>
      </template>
    </el-upload>

    <el-progress
      v-if="uploading"
      :percentage="uploadProgress"
      status="striped"
      striped-flow
      style="margin-top: 12px"
    />
  </div>
</template>
