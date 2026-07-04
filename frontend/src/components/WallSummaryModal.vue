<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, BarChart3, History, RefreshCw, Sparkles, X } from '@lucide/vue'
import type { WallSummary, WallSummaryDiff, WallSummaryHistoryItem } from '../types'

const props = defineProps<{
  summary: WallSummary | null
  history: WallSummaryHistoryItem[]
  diff: WallSummaryDiff | null
  loading: boolean
  historyLoading: boolean
  diffLoading: boolean
  diffError: string
  error: string
}>()

const emit = defineEmits<{
  close: []
  refresh: []
  compare: []
  openHistory: [item: WallSummaryHistoryItem]
}>()

const summaryTotal = computed(() => {
  if (!props.summary) return 0
  return Object.values(props.summary.sentiment_counts).reduce((sum, value) => sum + value, 0)
})

const sentimentItems = computed(() => {
  const counts = props.summary?.sentiment_counts
  const neutral = (counts?.neutral || 0) + (counts?.unknown || 0)
  return [
    { key: 'positive', label: '正向', value: counts?.positive || 0, tone: 'pos' },
    { key: 'neutral', label: '中性', value: neutral, tone: 'neu' },
    { key: 'negative', label: '负面', value: counts?.negative || 0, tone: 'neg' },
  ]
})

const currentSummaryLabel = computed(() => {
  if (!props.summary) return ''
  const time = new Date(props.summary.generated_at).toLocaleString([], {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
  return `${props.summary.cached ? '缓存摘要' : '新生成摘要'} · ${time}`
})

const leadPoint = computed(() => props.summary?.key_points[0])
const hasContent = computed(() => Boolean(props.summary))

function sentimentPercent(value: number) {
  if (!summaryTotal.value) return 0
  return Math.round((value / summaryTotal.value) * 100)
}

function severityLabel(value: string) {
  if (value === 'high') return '高'
  if (value === 'medium') return '中'
  if (value === 'low') return '低'
  return value || '待判断'
}

function signed(value: number) {
  if (value > 0) return `+${value}`
  return String(value)
}
</script>

<template>
  <div class="overlay" @mousedown.self="emit('close')">
    <section class="modal summary-modal">
      <button class="icon ghost close" type="button" @click="emit('close')"><X :size="18" /></button>
      <div class="summary-head">
        <h2>AI 摘要</h2>
        <p>主持人洞察</p>
        <div class="summary-head-actions">
          <button v-if="summary?.summary_id && !loading" class="secondary" type="button" :disabled="diffLoading" @click="emit('compare')">
            {{ diffLoading ? '对比中' : '对比上一版' }}
          </button>
          <button v-if="summary" class="secondary" type="button" :disabled="loading" @click="emit('refresh')">
            <RefreshCw :size="14" />{{ loading ? '更新中' : '重新生成' }}
          </button>
        </div>
      </div>

      <p v-if="loading && !hasContent" class="summary-muted">正在读取当前墙面评论...</p>
      <p v-if="error && !hasContent" class="form-error">{{ error }}</p>

      <template v-if="summary">
        <div class="summary-status">
          <span><Sparkles :size="14" />{{ currentSummaryLabel }}</span>
          <span>{{ summary.model }}</span>
          <span>{{ summary.thinking_enabled ? 'Thinking' : 'Non-thinking' }} · {{ summary.reasoning_effort }}</span>
          <span>{{ summary.card_count }} 张卡片</span>
        </div>
        <p v-if="loading" class="summary-inline-note">正在生成新版，当前面板先保留上一次可用结果。</p>
        <p v-else-if="error" class="summary-inline-note error">{{ error }}</p>

        <div class="summary-dashboard">
          <section class="summary-main">
            <article class="summary-brief">
              <span>关键结论</span>
              <h3>{{ leadPoint?.title || '当前反馈概览' }}</h3>
              <p>{{ leadPoint?.summary || summary.overview }}</p>
            </article>

            <section class="summary-section voices">
              <div class="summary-section-head">
                <h3>关键声音</h3>
                <span>{{ summary.key_points.length }} 组</span>
              </div>
              <article v-for="point in summary.key_points" :key="point.title" class="summary-block">
                <div>
                  <b>{{ point.title }}</b>
                  <p>{{ point.summary }}</p>
                </div>
                <ul v-if="point.evidence.length" class="evidence-snippets">
                  <li v-for="evidence in point.evidence" :key="evidence.id">{{ evidence.text }}</li>
                </ul>
              </article>
            </section>

            <section class="summary-section">
              <div class="summary-section-head">
                <h3>代表卡片证据</h3>
                <span>{{ summary.representative_cards.length }} 张</span>
              </div>
              <div class="evidence-list">
                <article v-for="card in summary.representative_cards" :key="card.id">
                  <p>{{ card.text }}</p>
                  <small>{{ card.sentiment || '未标注' }} · {{ card.reaction_count }} 个反应</small>
                </article>
              </div>
            </section>
          </section>

          <aside class="summary-side">
            <section class="summary-panel sentiment-panel">
              <div class="summary-section-head">
                <h3><BarChart3 :size="16" />情绪分布</h3>
                <span>{{ summaryTotal }} 条</span>
              </div>
              <div class="summary-bars">
                <span
                  v-for="item in sentimentItems"
                  :key="item.key"
                  :class="item.tone"
                  :style="{ width: `${sentimentPercent(item.value)}%` }"
                ></span>
              </div>
              <div class="summary-counts">
                <span v-for="item in sentimentItems" :key="item.key">
                  <b :class="item.tone"></b>{{ item.label }} {{ item.value }}
                </span>
              </div>
            </section>

            <section class="summary-panel risk-panel">
              <div class="summary-section-head">
                <h3><AlertTriangle :size="16" />风险提醒</h3>
                <span>{{ summary.risks.length }} 项</span>
              </div>
              <article v-for="risk in summary.risks" :key="risk.title" class="summary-risk">
                <span>{{ severityLabel(risk.severity) }}</span>
                <b>{{ risk.title }}</b>
                <p>{{ risk.summary }}</p>
                <small v-for="evidence in risk.evidence.slice(0, 2)" :key="evidence.id">{{ evidence.text }}</small>
              </article>
              <p v-if="!summary.risks.length" class="summary-empty">暂无明显风险</p>
            </section>

            <section v-if="history.length" class="summary-history summary-panel">
              <div class="summary-history-head">
                <b><History :size="15" />历史摘要</b>
                <span>{{ historyLoading ? '读取中' : `${history.length} 条` }}</span>
              </div>
              <button
                v-for="item in history"
                :key="item.id"
                type="button"
                :class="{ active: summary.cache_key === item.cache_key && summary.generated_at === item.generated_at }"
                @click="emit('openHistory', item)"
              >
                <span>{{ new Date(item.generated_at).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
                <small>{{ item.model }} · {{ item.thinking_enabled ? 'Thinking' : 'Non-thinking' }} · {{ item.card_count }} 张</small>
              </button>
            </section>
          </aside>
        </div>

        <section v-if="diff || diffError" class="summary-diff">
          <div class="summary-diff-head">
            <b>版本差异</b>
            <span v-if="diff">相比 {{ new Date(diff.against_generated_at).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span>
          </div>
          <p v-if="diffError" class="form-error">{{ diffError }}</p>
          <template v-else-if="diff">
            <div class="summary-diff-metrics">
              <span>卡片 {{ signed(diff.card_count_delta) }}</span>
              <span>正向 {{ signed(diff.sentiment_delta.positive) }}</span>
              <span>中性 {{ signed(diff.sentiment_delta.neutral + diff.sentiment_delta.unknown) }}</span>
              <span>负面 {{ signed(diff.sentiment_delta.negative) }}</span>
            </div>
            <div class="summary-diff-grid">
              <article>
                <b>新增观点</b>
                <small v-if="!diff.key_points_added.length">无明显新增</small>
                <span v-for="item in diff.key_points_added" :key="item">{{ item }}</span>
              </article>
              <article>
                <b>减少观点</b>
                <small v-if="!diff.key_points_removed.length">无明显减少</small>
                <span v-for="item in diff.key_points_removed" :key="item">{{ item }}</span>
              </article>
              <article>
                <b>新增风险</b>
                <small v-if="!diff.risks_added.length">无明显新增</small>
                <span v-for="item in diff.risks_added" :key="item">{{ item }}</span>
              </article>
              <article>
                <b>减少风险</b>
                <small v-if="!diff.risks_removed.length">无明显减少</small>
                <span v-for="item in diff.risks_removed" :key="item">{{ item }}</span>
              </article>
            </div>
          </template>
        </section>
      </template>
    </section>
  </div>
</template>
