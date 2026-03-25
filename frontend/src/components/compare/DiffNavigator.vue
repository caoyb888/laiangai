<script setup lang="ts">
import { computed } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import type { DiffItem } from '@/types/compare'

const props = defineProps<{
  items: DiffItem[]
  currentIndex: number
}>()

const emit = defineEmits<{ jumpTo: [index: number] }>()

// 导航条：按差异等级着色
const navItems = computed(() =>
  props.items.map((item, idx) => ({
    idx,
    level: item.diff_level,
    active: idx === props.currentIndex,
  }))
)

function colorForLevel(level: string): string {
  const map: Record<string, string> = {
    CRITICAL: 'var(--diff-risk-critical)',
    MAJOR:    'var(--diff-risk-major)',
    MINOR:    'var(--diff-risk-minor)',
  }
  return map[level] || '#ccc'
}
</script>

<template>
  <div class="diff-navigator">
    <div class="nav-label">差异导航 ({{ items.length }}处)</div>
    <div class="nav-track">
      <div
        v-for="nav in navItems"
        :key="nav.idx"
        class="nav-tick"
        :class="{ active: nav.active }"
        :style="{ background: colorForLevel(nav.level) }"
        :title="`#${nav.idx + 1} [${nav.level}]`"
        @click="emit('jumpTo', nav.idx)"
      />
    </div>
    <div class="nav-controls">
      <el-button
        size="small" circle :icon="ArrowUp"
        @click="emit('jumpTo', Math.max(0, currentIndex - 1))"
      />
      <span class="nav-pos">{{ currentIndex + 1 }} / {{ items.length }}</span>
      <el-button
        size="small" circle :icon="ArrowDown"
        @click="emit('jumpTo', Math.min(items.length - 1, currentIndex + 1))"
      />
    </div>
  </div>
</template>

<style scoped>
.diff-navigator {
  width: 48px; display: flex; flex-direction: column;
  align-items: center; padding: 8px 4px; background: #fafafa;
  border-left: 1px solid #ebeef5;
}
.nav-label { font-size: 10px; color: #909399; writing-mode: vertical-rl;
             text-orientation: mixed; margin-bottom: 8px; }
.nav-track { flex: 1; width: 8px; display: flex; flex-direction: column;
             gap: 2px; overflow: hidden; }
.nav-tick  { width: 8px; height: 4px; border-radius: 2px; cursor: pointer;
             opacity: 0.7; transition: opacity 0.15s; }
.nav-tick:hover  { opacity: 1; transform: scaleX(1.5); }
.nav-tick.active { opacity: 1; outline: 1px solid #409eff; }
.nav-controls { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.nav-pos  { font-size: 10px; color: #606266; }
</style>
