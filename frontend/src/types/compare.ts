export interface DiffItem {
  id: string
  seq_no: number
  diff_type: 'insert' | 'delete' | 'modify' | 'move'
  diff_level: 'CRITICAL' | 'MAJOR' | 'MINOR'
  doc_a_section: string | null
  doc_a_text: string | null
  doc_b_section: string | null
  doc_b_text: string | null
  semantic_desc: string | null
  risk_keywords: string | null
  is_reviewed: boolean
}

export interface CompareTask {
  task_id: string
  task_name: string | null
  status: 'pending' | 'processing' | 'done' | 'failed'
  progress: number
  total_diffs: number | null
  critical_diffs: number | null
  created_at: string
  finished_at: string | null
  doc_a_name?: string
  doc_b_name?: string
  error_msg?: string
}
