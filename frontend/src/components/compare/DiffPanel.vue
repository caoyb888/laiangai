<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import type { DiffItem } from '@/types/compare'

const props = defineProps<{
  diffItems: DiffItem[]
  docAName: string
  docBName: string
}>()

defineEmits<{
  reviewItem: [itemId: string]
}>()

const currentIndex = ref(0)
const filterLevel = ref<string>('ALL')

const filteredItems = computed(() => {
  if (filterLevel.value === 'ALL') return props.diffItems
  return props.diffItems.filter(i => i.diff_level === filterLevel.value)
})

// 跳转到指定差异项（供父组件通过 ref 调用）
function jumpTo(index: number) {
  currentIndex.value = index
  nextTick(() => {
    const scroller = document.getElementById('diff-scroller')
    scroller?.scrollTo({ top: index * 120, behavior: 'smooth' })
  })
}

function getDiffClass(item: DiffItem): string {
  const map: Record<string, string> = {
    insert: 'diff-insert',
    delete: 'diff-delete',
    modify: 'diff-modify',
    move:   'diff-move',
  }
  return map[item.diff_type] || ''
}

function getLevelTag(level: string): '' | 'danger' | 'warning' | 'success' {
  const map: Record<string, '' | 'danger' | 'warning' | 'success'> = {
    CRITICAL: 'danger',
    MAJOR:    'warning',
    MINOR:    'success',
  }
  return map[level] ?? ''
}

// 辅助函数：将文本用 <mark> 包裹高亮（简版，完整版用 char_spans 数据）
function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function renderText(text: string | null, type: 'insert' | 'delete'): string {
  if (!text) return '<span class="empty-text">（无内容）</span>'
  const cls = type === 'delete' ? 'diff-delete-mark' : 'diff-insert-mark'
  return `<span class="${cls}">${escapeHtml(text)}</span>`
}

// vue-virtual-scroller slot 类型为 unknown，用此辅助函数显式转型
function asItem(item: unknown): DiffItem {
  return item as DiffItem
}

// 暴露 jumpTo 供父组件（DiffNavigator）调用
defineExpose({ jumpTo })
</script>

<template>
  <div class="diff-panel">
    <!-- 工具栏 -->
    <div class="diff-toolbar">
      <el-radio-group v-model="filterLevel" size="small">
        <el-radio-button value="ALL">全部 ({{ diffItems.length }})</el-radio-button>
        <el-radio-button value="CRITICAL">
          <span style="color: var(--diff-risk-critical)">
            重大 ({{ diffItems.filter(i => i.diff_level === 'CRITICAL').length }})
          </span>
        </el-radio-button>
        <el-radio-button value="MAJOR">
          <span style="color: var(--diff-risk-major)">
            一般 ({{ diffItems.filter(i => i.diff_level === 'MAJOR').length }})
          </span>
        </el-radio-button>
        <el-radio-button value="MINOR">格式</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 双栏表头 -->
    <div class="diff-header">
      <div class="panel-label">📄 {{ docAName }}（基准）</div>
      <div></div>
      <div class="panel-label">📄 {{ docBName }}（对比）</div>
    </div>

    <!-- 虚拟滚动列表（长文档性能保障，见 CLAUDE.md §6.2）-->
    <DynamicScroller
      id="diff-scroller"
      class="diff-scroller"
      :items="filteredItems"
      :min-item-size="80"
      key-field="id"
    >
      <template #default="{ item, index, active }">
        <DynamicScrollerItem
          :item="item"
          :active="active"
          :data-index="index"
        >
          <div
            class="diff-row"
            :class="[getDiffClass(asItem(item)), { 'is-active': index === currentIndex }]"
            @click="currentIndex = index"
          >
            <!-- 左侧：文档A -->
            <div class="diff-cell cell-a">
              <div class="cell-meta">
                <el-tag :type="getLevelTag(asItem(item).diff_level)" size="small">
                  {{ asItem(item).diff_level }}
                </el-tag>
                <span class="seq-no">#{{ asItem(item).seq_no + 1 }}</span>
                <span class="section-path">{{ asItem(item).doc_a_section }}</span>
              </div>
              <div class="cell-text" v-html="renderText(asItem(item).doc_a_text, 'delete')" />
            </div>

            <!-- 分隔线 -->
            <div class="diff-divider">
              <el-icon><arrow-right /></el-icon>
            </div>

            <!-- 右侧：文档B -->
            <div class="diff-cell cell-b">
              <div class="cell-meta">
                <span class="section-path">{{ asItem(item).doc_b_section }}</span>
              </div>
              <div class="cell-text" v-html="renderText(asItem(item).doc_b_text, 'insert')" />
              <div v-if="asItem(item).semantic_desc" class="semantic-desc">
                💡 {{ asItem(item).semantic_desc }}
              </div>
              <div v-if="asItem(item).risk_keywords" class="risk-keywords">
                ⚠️ {{ asItem(item).risk_keywords }}
              </div>
            </div>
          </div>
        </DynamicScrollerItem>
      </template>
    </DynamicScroller>
  </div>
</template>

<style scoped>
.diff-panel { display: flex; flex-direction: column; height: 100%; flex: 1; min-width: 0; }

.diff-toolbar {
  padding: 8px 12px; background: #fff;
  border-bottom: 1px solid #dcdfe6;
}

.diff-header {
  display: grid; grid-template-columns: 1fr 40px 1fr;
  padding: 8px 12px; background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6; font-weight: 600;
}
.panel-label { font-size: 13px; color: #606266; }

.diff-scroller { flex: 1; }

.diff-row {
  display: grid; grid-template-columns: 1fr 40px 1fr;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer; transition: background 0.15s;
}
.diff-row:hover { background: #f0f9ff; }
.diff-row.is-active { background: #ecf5ff; outline: 2px solid #409eff; }

/* 使用 CSS 变量，禁止硬编码颜色，见 CLAUDE.md §6.2 */
.diff-insert .cell-b { background: var(--diff-insert-bg); }
.diff-delete .cell-a { background: var(--diff-delete-bg); }
.diff-modify .cell-a { background: var(--diff-delete-bg); }
.diff-modify .cell-b { background: var(--diff-insert-bg); }
.diff-move   { background: var(--diff-move-bg); }

.diff-insert-mark { background: var(--diff-insert-bg); color: var(--diff-insert-text); }
.diff-delete-mark { background: var(--diff-delete-bg); color: var(--diff-delete-text);
                    text-decoration: line-through; }

.diff-cell { padding: 10px 12px; }
.cell-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.seq-no    { font-size: 12px; color: #909399; }
.section-path { font-size: 11px; color: #c0c4cc; white-space: nowrap;
                overflow: hidden; text-overflow: ellipsis; max-width: 200px; }
.cell-text { font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.semantic-desc { margin-top: 6px; font-size: 12px; color: #409eff;
                 background: #ecf5ff; padding: 4px 8px; border-radius: 4px; }
.risk-keywords { margin-top: 4px; font-size: 12px; color: var(--diff-risk-critical); }

.diff-divider { display: flex; align-items: center; justify-content: center;
                background: #fafafa; border-left: 1px solid #ebeef5;
                border-right: 1px solid #ebeef5; color: #c0c4cc; }
.empty-text   { color: #c0c4cc; font-style: italic; }
</style>
