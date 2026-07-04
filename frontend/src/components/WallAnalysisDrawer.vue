<script setup lang="ts">
import { computed, ref, watch, type Component } from 'vue'
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  ClipboardList,
  Download,
  ExternalLink,
  FileText,
  Maximize2,
  Minimize2,
  RefreshCw,
  Sparkles,
  Tags,
  X,
} from '@lucide/vue'
import type { Card, ReactionType, WallSummary, WallSummaryHistoryItem } from '../types'
import {
  buildWallAnalysis,
  sentimentText,
  type AnalysisComment,
  type AnalysisTab,
  type AnalysisTone,
  type OverviewIssue,
} from '../utils/wallAnalysis'

type DrawerSize = 'drawer' | 'wide' | 'focus'
type AnalysisDetailType = 'sentiment' | 'topic' | 'issue'

const props = withDefaults(defineProps<{
  open?: boolean
  cards: Card[]
  summary: WallSummary | null
  history?: WallSummaryHistoryItem[]
  loading?: boolean
  historyLoading?: boolean
  error?: string
  initialTab?: AnalysisTab
  size?: DrawerSize
}>(), {
  open: true,
  history: () => [],
  loading: false,
  historyLoading: false,
  error: '',
  initialTab: 'overview',
  size: 'wide',
})

const emit = defineEmits<{
  close: []
  refreshSummary: []
  exportReport: []
  focusCards: [payload: { type: AnalysisDetailType; key: string; cardIds: string[] }]
  tabChange: [tab: AnalysisTab]
  toggleSize: []
}>()

const activeTab = ref<AnalysisTab>(props.initialTab)
const detail = ref<{ type: AnalysisDetailType; key: string } | null>(null)
const expandedSentiments = ref<Set<string>>(new Set())
const model = computed(() => buildWallAnalysis(props.cards, props.summary))

watch(() => props.initialTab, (tab) => {
  activeTab.value = tab
  detail.value = null
})

const tabs: Array<{ key: AnalysisTab; label: string; icon: Component }> = [
  { key: 'overview', label: '总览', icon: Sparkles },
  { key: 'sentiment', label: '情绪', icon: BarChart3 },
  { key: 'topic', label: '主题', icon: Tags },
  { key: 'summary', label: '摘要', icon: FileText },
]

const activeTitle = computed(() => {
  if (detail.value?.type === 'sentiment') return sentimentDetailGroup.value?.label || '情绪详情'
  if (detail.value?.type === 'topic') return topicDetailGroup.value?.label || '主题详情'
  if (detail.value?.type === 'issue') return issueDetail.value?.title || '议题详情'
  if (activeTab.value === 'sentiment') return '现场情绪'
  if (activeTab.value === 'topic') return '主题聚类'
  if (activeTab.value === 'summary') return '主持人简报'
  return '这面墙在说什么'
})

const statusLabel = computed(() => {
  if (props.loading) return '生成中'
  if (props.summary?.cached) return '缓存'
  if (props.summary) return '最新'
  return '本地分析'
})

const sentimentTotal = computed(() => model.value.sentimentGroups.reduce((sum, group) => sum + group.count, 0))
const sentimentDetailGroup = computed(() => {
  if (detail.value?.type !== 'sentiment') return null
  return model.value.sentimentGroups.find((group) => group.key === detail.value?.key) || null
})
const topicDetailGroup = computed(() => {
  if (detail.value?.type !== 'topic') return null
  return model.value.topicGroups.find((group) => group.key === detail.value?.key) || null
})
const issueDetail = computed(() => {
  if (detail.value?.type !== 'issue') return null
  return model.value.overviewIssues.find((issue) => issue.key === detail.value?.key) || null
})
const detailComments = computed<AnalysisComment[]>(() => {
  if (sentimentDetailGroup.value) return sentimentDetailGroup.value.allComments
  if (topicDetailGroup.value) return topicDetailGroup.value.allComments
  if (issueDetail.value) return issueDetail.value.allComments
  return []
})
const recentHistory = computed(() => props.history.slice(0, 4))
const reactionMeta: Array<{ type: ReactionType; label: string }> = [
  { type: 'like', label: '赞' },
  { type: 'dislike', label: '踩' },
  { type: 'question', label: '问' },
]

function setTab(tab: AnalysisTab) {
  activeTab.value = tab
  detail.value = null
  emit('tabChange', tab)
}

function openGroup(type: AnalysisDetailType, key: string, comments: AnalysisComment[]) {
  detail.value = { type, key }
  emit('focusCards', { type, key, cardIds: groupCardIds(comments) })
}

function openIssue(issue: OverviewIssue) {
  openGroup('issue', issue.key, issue.allComments)
}

function sentimentComments(group: { key: string; comments: AnalysisComment[]; allComments: AnalysisComment[] }) {
  return expandedSentiments.value.has(group.key) ? group.allComments : group.comments
}

function toggleSentimentGroup(key: string) {
  const next = new Set(expandedSentiments.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSentiments.value = next
}

function closeDetail() {
  detail.value = null
}

function toneClass(tone: AnalysisTone | null) {
  return `tone-${tone || 'neutral'}`
}

function toneLabel(tone: AnalysisTone | null) {
  if (tone === 'positive') return '偏正向'
  if (tone === 'negative') return '偏关注'
  if (tone === 'neutral') return '中性'
  return '主题'
}

function groupCardIds(comments: AnalysisComment[]) {
  return comments.map((comment) => comment.id)
}

function reactionBreakdown(comment: AnalysisComment) {
  if (!comment.reactionCounts) {
    return comment.reactionCount ? [{ type: 'total', label: '热度', count: comment.reactionCount }] : []
  }
  return reactionMeta
    .map((item) => ({ ...item, count: comment.reactionCounts?.[item.type] || 0 }))
    .filter((item) => item.count > 0)
}

function formatTime(value: string) {
  if (!value) return ''
  return new Date(value).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <aside v-if="open" class="analysis-drawer" :class="`size-${size}`">
    <header class="analysis-head">
      <div>
        <span class="analysis-kicker"><Sparkles :size="15" />AI 分析</span>
        <h2>{{ activeTitle }}</h2>
        <p>{{ model.subline }}</p>
      </div>
      <div class="analysis-head-actions">
        <span class="analysis-status">{{ statusLabel }}</span>
        <button class="analysis-icon" type="button" :title="size === 'focus' ? '收起' : '展开'" @click="emit('toggleSize')">
          <Minimize2 v-if="size === 'focus'" :size="18" />
          <Maximize2 v-else :size="18" />
        </button>
        <button class="analysis-icon" type="button" title="关闭" @click="emit('close')"><X :size="18" /></button>
      </div>
    </header>

    <nav class="analysis-tabs" aria-label="AI 分析">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key && !detail }"
        @click="setTab(tab.key)"
      >
        <component :is="tab.icon" :size="15" />
        {{ tab.label }}
      </button>
    </nav>

    <main class="analysis-body">
      <section v-if="detail" class="analysis-detail">
        <button class="analysis-back" type="button" @click="closeDetail">
          <ArrowLeft :size="16" />返回
        </button>
        <div class="detail-headline">
          <b>{{ activeTitle }}</b>
          <span>{{ detailComments.length }} 条</span>
        </div>
        <div class="comment-list detail-list">
          <article v-for="comment in detailComments" :key="comment.id" class="comment-row">
            <p>{{ comment.text }}</p>
            <footer>
              <span>{{ comment.authorName }}</span>
              <span>{{ sentimentText(comment.sentiment) }}</span>
              <span v-for="item in reactionBreakdown(comment)" :key="item.type" class="reaction-chip">
                {{ item.label }} {{ item.count }}
              </span>
            </footer>
          </article>
        </div>
      </section>

      <template v-else-if="activeTab === 'overview'">
        <section class="analysis-hero">
          <span>主判断</span>
          <h3>{{ model.headline }}</h3>
          <p>{{ model.subline }}</p>
        </section>

        <section class="metric-grid">
          <article>
            <b>{{ model.cardCount }}</b>
            <span>反馈</span>
          </article>
          <article>
            <b>{{ model.reactionCount }}</b>
            <span>互动</span>
          </article>
          <article>
            <b>{{ model.topicGroups.length }}</b>
            <span>主题</span>
          </article>
          <article>
            <b>{{ model.sentimentGroups.find((group) => group.key === 'negative')?.count || 0 }}</b>
            <span>关注</span>
          </article>
        </section>

        <section class="analysis-section issue-grid">
          <div class="section-head">
            <h3><ClipboardList :size="16" />核心议题</h3>
            <span>{{ model.overviewIssues.length }} 项</span>
          </div>
          <article v-for="issue in model.overviewIssues" :key="issue.key" class="issue-card">
            <header>
              <b>{{ issue.title }}</b>
              <span :class="toneClass(issue.tone)">{{ toneLabel(issue.tone) }}</span>
            </header>
            <p>{{ issue.body }}</p>
            <div class="issue-actions">
              <button type="button" @click="openIssue(issue)">
                <ExternalLink :size="14" />查看证据
              </button>
              <small>{{ issue.heat }} 互动</small>
            </div>
          </article>
        </section>

        <section class="prompt-strip">
          <b><AlertTriangle :size="16" />主持人可回应</b>
          <span v-for="prompt in model.prompts" :key="prompt">{{ prompt }}</span>
        </section>
      </template>

      <template v-else-if="activeTab === 'sentiment'">
        <section class="sentiment-panel">
          <div class="sentiment-legend">
            <span v-for="group in model.sentimentGroups" :key="group.key">
              <i :class="toneClass(group.tone)"></i>{{ group.compactLabel }} {{ group.percent }}%
            </span>
          </div>
          <div class="sentiment-bar" :aria-label="`情绪分布 ${sentimentTotal} 条`">
            <span
              v-for="group in model.sentimentGroups"
              :key="group.key"
              :class="toneClass(group.tone)"
              :style="{ width: `${Math.max(group.percent, group.count ? 5 : 0)}%` }"
            ></span>
          </div>
        </section>

        <section class="analysis-section sentiment-grid">
          <article v-for="group in model.sentimentGroups" :key="group.key" class="group-card" :class="toneClass(group.tone)">
            <header>
              <div>
                <b>{{ group.label }}</b>
                <small>{{ group.count }} 条 · {{ group.keywords.join(' / ') || '持续收集' }}</small>
              </div>
              <span>{{ group.percent }}%</span>
            </header>
            <div class="comment-list">
              <article v-for="comment in sentimentComments(group)" :key="comment.id" class="comment-row">
                <p>{{ comment.text }}</p>
                <footer>
                  <span>{{ comment.authorName }}</span>
                  <span v-for="item in reactionBreakdown(comment)" :key="item.type" class="reaction-chip">
                    {{ item.label }} {{ item.count }}
                  </span>
                </footer>
              </article>
            </div>
            <button v-if="group.hiddenCount" class="group-more" type="button" @click="toggleSentimentGroup(group.key)">
              {{ expandedSentiments.has(group.key) ? '收起' : `查看全部 ${group.count} 条` }}
            </button>
          </article>
        </section>
      </template>

      <template v-else-if="activeTab === 'topic'">
        <section class="topic-cloud">
          <button
            v-for="topic in model.topicGroups"
            :key="topic.key"
            type="button"
            :class="toneClass(topic.tone)"
            @click="openGroup('topic', topic.key, topic.allComments)"
          >
            <b>{{ topic.label }}</b>
            <span>{{ topic.count }} 条 · {{ topic.heat }}</span>
          </button>
        </section>

        <section class="analysis-section topic-grid">
          <article v-for="topic in model.topicGroups" :key="topic.key" class="topic-card">
            <header>
              <div>
                <b>{{ topic.label }}</b>
                <small>{{ topic.count }} 条 · {{ topic.percent }}%</small>
              </div>
              <span :class="toneClass(topic.tone)">{{ toneLabel(topic.tone) }}</span>
            </header>
            <p>{{ topic.summary }}</p>
            <div class="topic-keywords">
              <span v-for="keyword in topic.keywords" :key="keyword">#{{ keyword }}</span>
            </div>
            <div class="comment-list">
              <article v-for="comment in topic.comments" :key="comment.id" class="comment-row">
                <p>{{ comment.text }}</p>
                <footer>
                  <span>{{ comment.authorName }}</span>
                  <span v-for="item in reactionBreakdown(comment)" :key="item.type" class="reaction-chip">
                    {{ item.label }} {{ item.count }}
                  </span>
                </footer>
              </article>
            </div>
            <button class="group-more" type="button" @click="openGroup('topic', topic.key, topic.allComments)">
              查看主题
            </button>
          </article>
        </section>
      </template>

      <template v-else>
        <section v-if="loading && !summary" class="analysis-empty">
          <Sparkles :size="22" />
          <b>生成中</b>
          <span>正在整理最新反馈</span>
        </section>

        <section v-else-if="summary" class="summary-view">
          <article class="analysis-hero">
            <span>主判断</span>
            <h3>{{ summary.key_points[0]?.title || '当前反馈概览' }}</h3>
            <p>{{ summary.key_points[0]?.summary || summary.overview }}</p>
          </article>

          <section class="analysis-section issue-grid">
            <div class="section-head">
              <h3>关键议题</h3>
              <span>{{ summary.key_points.length }} 项</span>
            </div>
            <article v-for="point in summary.key_points" :key="point.title" class="issue-card">
              <header>
                <b>{{ point.title }}</b>
                <span>{{ point.evidence.length }} 证据</span>
              </header>
              <p>{{ point.summary }}</p>
              <div class="quote-list">
                <p v-for="evidence in point.evidence.slice(0, 2)" :key="evidence.id">
                  {{ evidence.text }}
                </p>
              </div>
            </article>
          </section>

          <section class="analysis-section risk-grid">
            <div class="section-head">
              <h3><AlertTriangle :size="16" />风险提醒</h3>
              <span>{{ summary.risks.length }} 项</span>
            </div>
            <article v-for="risk in summary.risks" :key="risk.title" class="risk-card">
              <span>{{ risk.severity === 'high' ? '高' : risk.severity === 'medium' ? '中' : '低' }}</span>
              <b>{{ risk.title }}</b>
              <p>{{ risk.summary }}</p>
            </article>
          </section>

          <section v-if="recentHistory.length" class="history-strip">
            <b>{{ historyLoading ? '读取中' : '历史摘要' }}</b>
            <span v-for="item in recentHistory" :key="item.id">{{ formatTime(item.generated_at) }}</span>
          </section>
        </section>

        <section v-else class="analysis-empty">
          <FileText :size="22" />
          <b>{{ error || '暂无摘要' }}</b>
          <span>可先生成主持人简报</span>
        </section>
      </template>
    </main>

    <footer class="analysis-foot">
      <button class="secondary-action" type="button" :disabled="loading" @click="emit('refreshSummary')">
        <RefreshCw :size="15" />{{ loading ? '生成中' : '重新生成' }}
      </button>
      <button class="primary-action" type="button" @click="emit('exportReport')">
        <Download :size="15" />导出报告
      </button>
    </footer>
  </aside>
</template>

<style scoped>
.analysis-drawer {
  position: fixed;
  inset: 0 0 0 auto;
  z-index: 980;
  width: min(920px, calc(100vw - 112px));
  min-width: 680px;
  height: 100vh;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  background: rgba(255,255,255,0.97);
  border-left: 1px solid #e6e9ef;
  box-shadow: -28px 0 60px rgba(20,22,32,0.18);
  color: #222631;
}
.analysis-drawer.size-drawer { width: min(720px, calc(100vw - 128px)); min-width: 560px; }
.analysis-drawer.size-wide { width: min(1040px, calc(100vw - 96px)); }
.analysis-drawer.size-focus { width: min(1240px, calc(100vw - 56px)); }
.analysis-head {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  padding: 28px 30px 18px;
  border-bottom: 1px solid #eef0f4;
}
.analysis-kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #5b5bf0;
  font-size: 13px;
  font-weight: 900;
}
.analysis-head h2 {
  margin: 9px 0 7px;
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: 0;
}
.analysis-head p {
  margin: 0;
  color: #7a808d;
  font-size: 14px;
  line-height: 1.5;
}
.analysis-head-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.analysis-status {
  border-radius: 999px;
  padding: 6px 10px;
  background: #f0f1ff;
  color: #5b5bf0;
  font-size: 12px;
  font-weight: 900;
}
.analysis-icon {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #f5f6f8;
  color: #68707f;
  cursor: pointer;
}
.analysis-tabs {
  display: flex;
  gap: 6px;
  padding: 12px 30px;
  border-bottom: 1px solid #eef0f4;
}
.analysis-tabs button {
  min-height: 36px;
  border: none;
  border-radius: 999px;
  padding: 0 13px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: transparent;
  color: #69707d;
  font-weight: 850;
  cursor: pointer;
}
.analysis-tabs button.active {
  background: #171922;
  color: #fff;
}
.analysis-body {
  min-height: 0;
  overflow: auto;
  padding: 18px 30px 24px;
}
.analysis-hero {
  border-radius: 8px;
  padding: 22px;
  background: #222633;
  color: #fff;
}
.analysis-hero span {
  color: rgba(255,255,255,0.68);
  font-size: 12px;
  font-weight: 900;
}
.analysis-hero h3 {
  margin: 8px 0;
  font-size: 24px;
  line-height: 1.32;
  letter-spacing: 0;
}
.analysis-hero p {
  margin: 0;
  color: rgba(255,255,255,0.76);
  line-height: 1.72;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}
.metric-grid article {
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 13px;
  background: #fff;
}
.metric-grid b {
  display: block;
  font-size: 24px;
  line-height: 1;
}
.metric-grid span {
  display: block;
  margin-top: 7px;
  color: #7a808d;
  font-size: 12px;
  font-weight: 850;
}
.analysis-section {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.analysis-section.issue-grid,
.analysis-section.topic-grid {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  align-items: start;
}
.analysis-section.sentiment-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: start;
}
.analysis-section.risk-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.section-head {
  grid-column: 1 / -1;
}
.section-head,
.detail-headline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.section-head h3 {
  margin: 0;
  display: inline-flex;
  gap: 7px;
  align-items: center;
  font-size: 15px;
}
.section-head span,
.detail-headline span {
  color: #8b909c;
  font-size: 12px;
  font-weight: 900;
}
.issue-card,
.topic-card,
.group-card,
.risk-card {
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 15px;
  background: #fff;
}
.issue-card header,
.topic-card header,
.group-card header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
}
.issue-card b,
.topic-card b,
.group-card b,
.risk-card b {
  display: block;
  font-size: 15px;
}
.issue-card p,
.topic-card p,
.risk-card p {
  margin: 9px 0 0;
  color: #555d6c;
  line-height: 1.68;
}
.issue-card header span,
.topic-card header > span,
.risk-card > span {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 5px 9px;
  font-size: 12px;
  font-weight: 900;
}
.tone-positive { background: #e1f6eb; color: #148650; }
.tone-neutral { background: #edf1f5; color: #64707f; }
.tone-negative { background: #ffe4e1; color: #c84339; }
.tone-topic { background: #eeeefe; color: #5b5bf0; }
.issue-actions {
  margin-top: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.issue-actions button,
.group-more,
.analysis-back {
  border: none;
  border-radius: 999px;
  min-height: 32px;
  padding: 0 11px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f2f3f6;
  color: #4f5663;
  font-size: 12px;
  font-weight: 900;
  cursor: pointer;
}
.issue-actions small {
  color: #8b909c;
  font-weight: 850;
}
.prompt-strip {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 13px;
  background: #fffaf0;
}
.prompt-strip b {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 6px;
}
.prompt-strip span {
  border-radius: 999px;
  background: #fff;
  padding: 6px 10px;
  color: #a05e00;
  font-size: 12px;
  font-weight: 900;
}
.sentiment-panel {
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 15px;
  background: #fff;
}
.sentiment-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 12px;
}
.sentiment-legend span {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  color: #606878;
  font-size: 13px;
  font-weight: 850;
}
.sentiment-legend i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
.sentiment-bar {
  height: 14px;
  display: flex;
  overflow: hidden;
  border-radius: 999px;
  background: #edf0f4;
}
.sentiment-bar span {
  min-width: 0;
}
.group-card {
  display: grid;
  gap: 12px;
  border-left-width: 4px;
}
.group-card.tone-positive { border-left-color: #34c47f; background: #fbfffd; }
.group-card.tone-neutral { border-left-color: #aab0ba; background: #fff; }
.group-card.tone-negative { border-left-color: #ef5f57; background: #fffafa; }
.group-card small {
  display: block;
  margin-top: 4px;
  color: #7a808d;
  font-size: 12px;
}
.comment-list {
  display: grid;
  gap: 8px;
}
.comment-row {
  border-radius: 7px;
  padding: 9px 10px;
  background: #f8f9fb;
}
.comment-row p {
  margin: 0;
  color: #343945;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.detail-list .comment-row p {
  -webkit-line-clamp: 4;
}
.comment-row footer {
  margin-top: 7px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: #8b909c;
  font-size: 12px;
  font-weight: 800;
}
.reaction-chip {
  border-radius: 999px;
  min-height: 22px;
  padding: 2px 7px;
  display: inline-flex;
  align-items: center;
  background: #fff;
  color: #596170;
  font-size: 11px;
  font-weight: 900;
}
.topic-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}
.topic-cloud button {
  border: none;
  border-radius: 999px;
  min-height: 42px;
  padding: 7px 13px;
  display: inline-flex;
  align-items: center;
  gap: 9px;
  cursor: pointer;
}
.topic-cloud b {
  font-size: 13px;
}
.topic-cloud span {
  color: inherit;
  opacity: 0.75;
  font-size: 12px;
  font-weight: 900;
}
.topic-card {
  display: grid;
  gap: 12px;
}
.topic-card small {
  color: #7a808d;
}
.topic-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.topic-keywords span {
  border-radius: 999px;
  padding: 5px 8px;
  background: #f2f3f6;
  color: #69707d;
  font-size: 12px;
  font-weight: 850;
}
.quote-list {
  display: grid;
  gap: 8px;
  margin-top: 11px;
}
.quote-list p {
  margin: 0;
  border-left: 3px solid #5b5bf0;
  border-radius: 6px;
  padding: 9px 10px;
  background: #f8f9fb;
  color: #5a6270;
  line-height: 1.55;
}
.risk-card {
  display: grid;
  gap: 7px;
}
.risk-card > span {
  justify-self: start;
}
.history-strip {
  margin-top: 16px;
  border: 1px solid #edf0f4;
  border-radius: 8px;
  padding: 13px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  background: #fff;
}
.history-strip b {
  margin-right: 6px;
}
.history-strip span {
  border-radius: 999px;
  padding: 5px 9px;
  background: #f2f3f6;
  color: #69707d;
  font-size: 12px;
  font-weight: 850;
}
.analysis-empty {
  min-height: 280px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  color: #8b909c;
}
.analysis-empty b {
  color: #222631;
  font-size: 16px;
}
.analysis-detail {
  display: grid;
  gap: 14px;
}
.analysis-back {
  justify-self: start;
}
.analysis-foot {
  border-top: 1px solid #eef0f4;
  padding: 14px 30px 18px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.secondary-action,
.primary-action {
  border: none;
  border-radius: 999px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 900;
  cursor: pointer;
}
.secondary-action {
  background: #f4f5f7;
  color: #3f4652;
}
.primary-action {
  background: #171922;
  color: #fff;
}
.secondary-action:disabled {
  opacity: 0.55;
  cursor: wait;
}
@media (max-width: 900px) {
  .analysis-drawer,
  .analysis-drawer.size-drawer,
  .analysis-drawer.size-wide,
  .analysis-drawer.size-focus {
    width: 100vw;
    min-width: 0;
  }
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .analysis-section.issue-grid,
  .analysis-section.topic-grid,
  .analysis-section.sentiment-grid,
  .analysis-section.risk-grid {
    grid-template-columns: 1fr;
  }
  .analysis-head,
  .analysis-tabs,
  .analysis-body,
  .analysis-foot {
    padding-left: 18px;
    padding-right: 18px;
  }
}
</style>
