<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import DiffMatchPatch from 'diff-match-patch'
import type { DiffItem } from '@/types/compare'

const props = defineProps<{
  diffItems: DiffItem[]
  docAName: string
  docBName: string
}>()

defineEmits<{
  reviewItem: [itemId: string]
}>()

const dmp = new DiffMatchPatch()

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

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/**
 * 对 modify 类型进行字符级 diff，渲染左栏（删除标记）
 * 仅提取 EQUAL(-0) 和 DELETE(-1) 操作，INSERT 在右栏展示
 */
function renderModifyA(textA: string, textB: string): string {
  const diffs = dmp.diff_main(textA, textB)
  dmp.diff_cleanupSemantic(diffs)
  return diffs
    .filter(([op]) => op !== DiffMatchPatch.DIFF_INSERT)
    .map(([op, text]) => {
      const escaped = escapeHtml(text)
      if (op === DiffMatchPatch.DIFF_DELETE) {
        return `<span class="diff-delete-mark">${escaped}</span>`
      }
      return escaped
    })
    .join('')
}

/**
 * 对 modify 类型进行字符级 diff，渲染右栏（新增标记）
 * 仅提取 EQUAL(0) 和 INSERT(1) 操作，DELETE 在左栏展示
 */
function renderModifyB(textA: string, textB: string): string {
  const diffs = dmp.diff_main(textA, textB)
  dmp.diff_cleanupSemantic(diffs)
  return diffs
    .filter(([op]) => op !== DiffMatchPatch.DIFF_DELETE)
    .map(([op, text]) => {
      const escaped = escapeHtml(text)
      if (op === DiffMatchPatch.DIFF_INSERT) {
        return `<span class="diff-insert-mark">${escaped}</span>`
      }
      return escaped
    })
    .join('')
}

/**
 * 非 modify 类型的整块渲染（delete / insert / move）
 */
function renderText(text: string | null, type: 'insert' | 'delete' | 'move'): string {
  if (!text) return '<span class="empty-text">（无内容）</span>'
  const escaped = escapeHtml(text)
  if (type === 'delete') return `<span class="diff-delete-mark">${escaped}</span>`
  if (type === 'insert') return `<span class="diff-insert-mark">${escaped}</span>`
  return `<span class="diff-move-mark">${escaped}</span>`
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
              <!-- modify：字符级高亮；其他类型：整块标记 -->
              <div
                class="cell-text"
                v-html="asItem(item).diff_type === 'modify'
                  ? renderModifyA(asItem(item).doc_a_text ?? '', asItem(item).doc_b_text ?? '')
                  : renderText(asItem(item).doc_a_text, asItem(item).diff_type === 'insert' ? 'insert' : asItem(item).diff_type === 'move' ? 'move' : 'delete')"
              />
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
              <!-- modify：字符级高亮；其他类型：整块标记 -->
              <div
                class="cell-text"
                v-html="asItem(item).diff_type === 'modify'
                  ? renderModifyB(asItem(item).doc_a_text ?? '', asItem(item).doc_b_text ?? '')
                  : renderText(asItem(item).doc_b_text, asItem(item).diff_type === 'delete' ? 'delete' : asItem(item).diff_type === 'move' ? 'move' : 'insert')"
              />
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

/* 字符级内联高亮标记（见 CLAUDE.md §6.2，颜色通过 CSS 变量统一管理）*/
.diff-insert-mark {
  background: var(--diff-insert-bg);
  color: var(--diff-insert-text);
  border-radius: 2px;
  padding: 0 1px;
}
.diff-delete-mark {
  background: var(--diff-delete-bg);
  color: var(--diff-delete-text);
  text-decoration: line-through;
  border-radius: 2px;
  padding: 0 1px;
}
.diff-move-mark {
  background: var(--diff-move-bg);
  color: var(--diff-move-text);
  border-radius: 2px;
  padding: 0 1px;
}

.diff-cell { padding: 10px 12px; }
.cell-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.seq-no    { font-size: 12px; color: #909399; }
.section-path { font-size: 11px; color: #c0c4cc; white-space: nowrap;
                overflow: hidden; text-overflow: ellipsis; max-width: 200px; }
.cell-text { font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
.semantic-desc { margin-top: 6px; font-size: 12px; color: #409eff;
                 background: #ecf5ff; padding: 4px 8px; border-radius: 4px; }
.risk-keywords { margin-top: 4px; font-size: 12px; color: var(--diff-risk-critical);
                 font-weight: 600; }

.diff-divider { display: flex; align-items: center; justify-content: center;
                background: #fafafa; border-left: 1px solid #ebeef5;
                border-right: 1px solid #ebeef5; color: #c0c4cc; }
.empty-text   { color: #c0c4cc; font-style: italic; }
</style>
