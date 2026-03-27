<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
</script>

<template>
  <el-tooltip
    :content="themeStore.theme === 'tech' ? '切换为极简白风格' : '切换为深蓝科技风格'"
    placement="bottom"
  >
    <el-button
      class="theme-switcher"
      :class="themeStore.theme"
      size="small"
      @click="themeStore.toggle()"
    >
      <span v-if="themeStore.theme === 'tech'" class="switcher-icon">☀</span>
      <span v-else class="switcher-icon">◈</span>
      {{ themeStore.theme === 'tech' ? '极简白' : '深蓝科技' }}
    </el-button>
  </el-tooltip>
</template>

<style scoped>
.theme-switcher {
  font-size: 12px;
  transition: all 0.2s;
}

.theme-switcher.minimal {
  background: transparent;
  border: 1px solid #2563eb;
  color: #2563eb;
}

.theme-switcher.minimal:hover {
  background: #eff6ff;
}

.theme-switcher.tech {
  background: transparent;
  border: 1px solid rgba(96, 165, 250, 0.6);
  color: #93c5fd;
}

.theme-switcher.tech:hover {
  background: rgba(96, 165, 250, 0.1);
  border-color: #93c5fd;
}

.switcher-icon {
  margin-right: 4px;
}
</style>
