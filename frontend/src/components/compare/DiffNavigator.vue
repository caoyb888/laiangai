<script setup lang="ts">
import { computed } from 'vue'
import type { DiffItem } from '@/types/compare'

const props = defineProps<{
  items: DiffItem[]
  currentIndex: number
}>()

const emit = defineEmits<{ jumpTo: [index: number] }>()

const navItems = computed(() =>
  props.items.map((item, idx) => ({
    idx,
    level: item.diff_level,
    type: item.diff_type,
    textA: item.doc_a_text,
    textB: item.doc_b_text,
    active: idx === props.currentIndex,
  }))
)

function tagType(level: string): '' | 'danger' | 'warning' | 'success' {
  const map: Record<string, '' | 'danger' | 'warning' | 'success'> = {
    CRITICAL: 'danger',
    MAJOR:    'warning',
    MINOR:    'success',
  }
  return map[level] || ''
}

function levelLabel(level: string): string {
  const map: Record<string, string> = { CRITICAL: '重大', MAJOR: '一般', MINOR: '格式' }
  return map[level] || level
}

function snippet(text: string | null | undefined): string {
  if (!text) return '（空）'
  return text.length > 40 ? text.slice(0, 40) + '…' : text
}
</script>

<template>
  <div class="diff-navigator">
    <div class="nav-header">
      差异导航
      <span class="nav-count">{{ items.length }} 处</span>
    </div>

    <div v-if="items.length === 0" class="nav-empty">暂无差异</div>

    <div v-else class="nav-list">
      <div
        v-for="nav in navItems"
        :key="nav.idx"
        class="nav-item"
        :class="{ active: nav.active }"
        @click="emit('jumpTo', nav.idx)"
      >
        <div class="nav-item-top">
          <span class="nav-seq">#{{ nav.idx + 1 }}</span>
          <el-tag :type="tagType(nav.level)" size="small" effect="plain">
            {{ levelLabel(nav.level) }}
          </el-tag>
        </div>
        <div class="nav-item-text">{{ snippet(nav.textA || nav.textB) }}</div>
      </div>
    </div>

    <div v-if="items.length > 0" class="nav-footer">
      <el-button
        size="small" text
        :disabled="currentIndex <= 0"
        @click="emit('jumpTo', currentIndex - 1)"
      >上一处</el-button>
      <span class="nav-pos">{{ currentIndex + 1 }} / {{ items.length }}</span>
      <el-button
        size="small" text
        :disabled="currentIndex >= items.length - 1"
        @click="emit('jumpTo', currentIndex + 1)"
      >下一处</el-button>
    </div>
  </div>
</template>

<style scoped>
.diff-navigator {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border-left: 1px solid #ebeef5;
  overflow: hidden;
}

.nav-header {
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.nav-count {
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}

.nav-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  font-size: 13px;
}

.nav-list {
  flex: 1;
  overflow-y: auto;
}

.nav-item {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.15s;
}

.nav-item:hover { background: #f0f9ff; }
.nav-item.active { background: #ecf5ff; border-left: 3px solid #409eff; }

.nav-item-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.nav-seq {
  font-size: 11px;
  color: #c0c4cc;
}

.nav-item-text {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  word-break: break-all;
}

.nav-footer {
  padding: 8px 12px;
  border-top: 1px solid #ebeef5;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.nav-pos {
  font-size: 12px;
  color: #909399;
}
</style>
