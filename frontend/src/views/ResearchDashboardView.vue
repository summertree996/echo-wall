<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Activity,
  ArrowLeft,
  BarChart3,
  CalendarClock,
  Clock3,
  Download,
  FileDown,
  Gauge,
  LayoutDashboard,
  LineChart,
  ListChecks,
  Lock,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  StickyNote,
  Users,
} from '@lucide/vue'
import LoginModal from '../components/LoginModal.vue'
import { api } from '../services/api'
import { useAuthStore } from '../stores/auth'
import type { ResearchDashboard, ResearchDashboardPoint, ResearchTimelineEvent } from '../types'

type HeatMode = 'all' | 'ui:click' | 'pointer:sample' | 'card:visible'
type EventCategory = 'content' | 'reaction' | 'behavior' | 'system' | 'default'
type ResearchSection = 'overview' | 'realtime' | 'analysis' | 'participants' | 'content' | 'events' | 'exports'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dashboard = ref<ResearchDashboard | null>(null)
const loading = ref(false)
const error = ref('')
const showLogin = ref(false)
const heatMode = ref<HeatMode>('all')
const selectedUserId = ref<string>('')
const eventQuery = ref('')
const contentQuery = ref('')
const activeSection = ref<ResearchSection>('overview')
const archiving = ref(false)

const exportSchemas = [
  {
    key: 'research',
    title: '科研行为 CSV',
    note: '全量时间线，合并便签快照、反应、业务操作和前端行为事件。',
    fields: [
      ['source', '事件来源，card、reaction、action_log 或 research_event'],
      ['id', '该来源表内的事件或对象 ID'],
      ['wall_id', '所属反馈墙 ID'],
      ['user_id', '用户 ID，匿名访客为空'],
      ['user_name', '用户昵称'],
      ['email', '注册用户邮箱'],
      ['client_session_id', '前端采集会话 ID'],
      ['event_type', '事件类型，如 ui:click、card:visible、reaction:like'],
      ['target_type', '事件对象类型，如 card、wall、summary'],
      ['target_id', '事件对象 ID'],
      ['plain_text', '便签正文，非内容事件为空'],
      ['x / y', '事件在画布上的坐标'],
      ['payload_json', '事件扩展数据，保留原始结构'],
      ['client_ts', '客户端事件时间'],
      ['created_at', '服务端入库或业务发生时间'],
    ],
  },
  {
    key: 'cards',
    title: '反馈内容 CSV',
    note: '便签内容快照，用于内容分析、情绪统计和反馈引用。',
    fields: [
      ['id', '便签 ID'],
      ['author_name', '作者昵称，匿名墙显示匿名成员'],
      ['plain_text', '便签正文'],
      ['sentiment', '情绪标签 positive、neutral、negative'],
      ['topics', '主题标签，用分号连接'],
      ['like / dislike / question', '三类反应计数'],
      ['created_at', '便签创建时间'],
      ['updated_at', '便签最后更新时间'],
    ],
  },
  {
    key: 'actions',
    title: '业务操作 CSV',
    note: '后端业务审计日志，用于追踪墙管理、便签操作和导出行为。',
    fields: [
      ['id', '操作日志 ID'],
      ['user_id', '操作者用户 ID'],
      ['user_name', '操作者昵称'],
      ['action_type', '操作类型，如 card:create、wall:summary'],
      ['payload_json', '操作参数和目标对象'],
      ['created_at', '操作发生时间'],
    ],
  },
]

const navItems = [
  { key: 'overview', label: '研究概览', icon: LayoutDashboard },
  { key: 'realtime', label: '实时看板', icon: Gauge },
  { key: 'analysis', label: '数据分析', icon: LineChart },
  { key: 'participants', label: '参与者', icon: Users },
  { key: 'content', label: '反馈内容', icon: StickyNote },
  { key: 'events', label: '事件日志', icon: ListChecks },
  { key: 'exports', label: '导出记录', icon: FileDown },
] satisfies Array<{ key: ResearchSection; label: string; icon: unknown }>

const wallId = computed(() => String(route.params.wallId))
const currentAdminName = computed(() => auth.user?.nickname || '管理员')
const activeUser = computed(() => dashboard.value?.users.find((user) => user.user_id === selectedUserId.value) || null)
const maxTimelineOffset = computed(() => Math.max(1, ...(dashboard.value?.timeline.map((event) => event.offset_seconds) || [1])))

const filteredTimeline = computed(() => {
  const data = dashboard.value?.timeline || []
  return data.filter(matchesFilters)
})

const eventRows = computed(() => {
  const rows = dashboard.value?.event_rows || []
  const query = eventQuery.value.trim().toLowerCase()
  return rows.filter((event) => {
    if (!matchesFilters(event)) return false
    if (!query) return true
    return `${event.user_name} ${event.event_type} ${event.plain_text} ${event.target_id || ''}`.toLowerCase().includes(query)
  })
})

const displayedRows = computed(() => {
  const limit = activeSection.value === 'events' ? 80 : 9
  return eventRows.value.slice(0, limit)
})

const contentRows = computed(() => {
  const cards = dashboard.value?.cards || []
  const query = contentQuery.value.trim().toLowerCase()
  return cards.filter((card) => {
    if (selectedUserId.value && card.author_id !== selectedUserId.value) return false
    if (!query) return true
    return `${card.author_name} ${card.plain_text} ${card.sentiment || ''}`.toLowerCase().includes(query)
  })
})

const latestEvents = computed(() => [...filteredTimeline.value].sort((a, b) => eventMillis(b.created_at) - eventMillis(a.created_at)).slice(0, 16))
const recentUserRows = computed(() => [...participationRows.value].sort((a, b) => eventMillis(b.user.last_seen) - eventMillis(a.user.last_seen)).slice(0, 8))
const latestCards = computed(() => [...contentRows.value].sort((a, b) => eventMillis(b.created_at) - eventMillis(a.created_at)).slice(0, 8))

const filteredHeatPoints = computed(() => {
  const points = dashboard.value?.heatmap_points || []
  return points.filter((point) => {
    if (heatMode.value !== 'all' && point.event_type !== heatMode.value) return false
    if (selectedUserId.value && point.user_id !== selectedUserId.value) return false
    return true
  })
})

const metricCards = computed(() => {
  if (!dashboard.value) return []
  const metrics = dashboard.value.metrics
  return [
    { label: '参与人数', value: metrics.participants, suffix: '', delta: '+2', tone: 'blue', icon: Users },
    { label: '便签总数', value: metrics.cards, suffix: '', delta: '+5', tone: 'green', icon: StickyNote },
    { label: '反应总数', value: metrics.reactions, suffix: '', delta: '+28', tone: 'yellow', icon: Gauge },
    { label: '行为事件', value: metrics.total_events, suffix: '', delta: '+76', tone: 'purple', icon: Activity },
    { label: '时间跨度', value: formatClock(metrics.active_span_seconds), suffix: '', delta: `开始时间 ${formatClockTime(metrics.started_at)}`, tone: 'cyan', icon: Clock3 },
  ]
})

const participationRows = computed(() => {
  const users = dashboard.value?.users || []
  const raw = users.map((user) => ({
    user,
    score: user.event_count + user.card_count * 8 + user.reaction_count * 3,
  }))
  const max = Math.max(1, ...raw.map((row) => row.score))
  return raw
    .sort((a, b) => b.score - a.score)
    .map((row, index) => ({
      ...row,
      rank: index + 1,
      normalized: Math.round((row.score / max) * 100),
    }))
})

const timelineSeries = computed(() => {
  const bins = 12
  const categories: Array<{ key: EventCategory; label: string; color: string }> = [
    { key: 'content', label: '便签创建', color: '#2f6fed' },
    { key: 'reaction', label: '反应', color: '#2aae7b' },
    { key: 'behavior', label: '浏览行为', color: '#8a62dc' },
    { key: 'system', label: '系统事件', color: '#f28c28' },
  ]
  const bucketed = categories.map((category) => ({
    ...category,
    values: Array.from({ length: bins }, () => 0),
  }))
  filteredTimeline.value.forEach((event) => {
    const category = eventTone(event.event_type)
    const series = bucketed.find((item) => item.key === category)
    if (!series) return
    const index = Math.min(bins - 1, Math.max(0, Math.floor((event.offset_seconds / maxTimelineOffset.value) * (bins - 1))))
    series.values[index] += 1
  })
  const maxCount = Math.max(1, ...bucketed.flatMap((series) => series.values))
  return bucketed.map((series) => ({
    ...series,
    points: series.values.map((count, index) => {
      const x = 24 + (index / (bins - 1)) * 592
      const y = 142 - (count / maxCount) * 108
      return `${x.toFixed(1)},${y.toFixed(1)}`
    }).join(' '),
  }))
})

const eventBreakdown = computed(() => {
  const categories: Array<{ key: EventCategory; label: string; color: string; count: number }> = [
    { key: 'content', label: '便签创建', color: '#2f6fed', count: 0 },
    { key: 'reaction', label: '反应', color: '#2aae7b', count: 0 },
    { key: 'behavior', label: '浏览行为', color: '#8a62dc', count: 0 },
    { key: 'system', label: '系统事件', color: '#f28c28', count: 0 },
    { key: 'default', label: '其他事件', color: '#cbd5e1', count: 0 },
  ]
  filteredTimeline.value.forEach((event) => {
    const category = eventTone(event.event_type)
    const row = categories.find((item) => item.key === category) || categories[categories.length - 1]
    row.count += 1
  })
  const total = Math.max(1, categories.reduce((sum, item) => sum + item.count, 0))
  return categories.map((item) => ({ ...item, percent: Math.round((item.count / total) * 1000) / 10 }))
})

const donutStyle = computed(() => {
  let cursor = 0
  const segments = eventBreakdown.value.map((item) => {
    const start = cursor
    cursor += item.percent
    return `${item.color} ${start}% ${cursor}%`
  })
  return { background: `conic-gradient(${segments.join(', ')})` }
})

const sectionSummary = computed(() => {
  const labels: Record<ResearchSection, string> = {
    overview: '总览当前墙面的行为采集、参与度、注意力分布和最新事件。',
    realtime: '聚焦最新入库事件、最近活跃用户和最新反馈内容。',
    analysis: '基于已采集事件做趋势、类型占比和行为结构分析。',
    participants: '查看每位参与者的发言、反应、行为事件和活跃时长。',
    content: '查看反馈便签内容、情绪标签、互动数量和作者来源。',
    events: '查看可追溯的原始事件序列，支持按用户、事件和文本筛选。',
    exports: '导出科研行为、反馈内容和业务操作数据，支持按用户导出。',
  }
  return labels[activeSection.value]
})

const eventTableTitle = computed(() => {
  if (activeSection.value === 'events') return `原始事件日志（${eventRows.value.length} 条）`
  return `原始事件记录（最新 ${displayedRows.value.length} 条）`
})

function matchesFilters(event: ResearchTimelineEvent) {
  if (selectedUserId.value && event.user_id !== selectedUserId.value) return false
  return true
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const user = await auth.refreshSession()
    if (!user) {
      showLogin.value = true
      return
    }
    if (!user.is_admin) {
      router.push('/')
      return
    }
    dashboard.value = await api.researchDashboard(wallId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '科研看板读取失败'
  } finally {
    loading.value = false
  }
}

function closeLogin() {
  showLogin.value = false
  void load()
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`
  return `${(seconds / 3600).toFixed(1)}小时`
}

function formatClock(seconds: number) {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function formatTime(value: string | null) {
  if (!value) return '未记录'
  return new Date(value).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function eventMillis(value: string | null) {
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}

function formatClockTime(value: string | null) {
  if (!value) return '--:--'
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function eventLabel(type: string) {
  const labels: Record<string, string> = {
    'card:authored': '便签创建',
    'card:create': '便签创建',
    'card:update': '便签编辑',
    'card:move': '便签移动',
    'card:reaction': '反应',
    'card:visible': '便签曝光',
    'card:detail_open': '打开详情',
    'ui:click': '点击',
    'pointer:sample': '鼠标采样',
    'stage:scroll': '滚动',
    'tool:change': '工具切换',
    'wall:view': '进入墙面',
    'wall:organize_enter': '进入整理',
    'wall:organize_topic': '主题整理',
    'wall:organize_sentiment': '情绪整理',
    'wall:spotlight': '聚焦卡片',
    'wall:summary': '生成摘要',
    'session:start': '会话开始',
    'session:end': '会话结束',
    'reaction:like': '赞同',
    'reaction:dislike': '保留意见',
    'reaction:question': '想追问',
  }
  return labels[type] || type
}

function eventTone(type: string): EventCategory {
  if (type.includes('visible') || type.includes('pointer') || type.includes('scroll') || type.includes('click')) return 'behavior'
  if (type.includes('reaction')) return 'reaction'
  if (type.includes('card')) return 'content'
  if (type.includes('wall') || type.includes('session') || type.includes('tool')) return 'system'
  return 'default'
}

function pointStyle(point: ResearchDashboardPoint) {
  if (!dashboard.value) return {}
  const left = Math.min(100, Math.max(0, (point.x / dashboard.value.wall.canvas_width) * 100))
  const top = Math.min(100, Math.max(0, (point.y / dashboard.value.wall.canvas_height) * 100))
  const size = Math.min(210, Math.max(54, 54 + point.weight * 82))
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${size}px`,
    height: `${size}px`,
  }
}

function cardStyle(card: ResearchDashboard['cards'][number]) {
  if (!dashboard.value) return {}
  return {
    left: `${Math.min(97, Math.max(3, (card.x / dashboard.value.wall.canvas_width) * 100))}%`,
    top: `${Math.min(95, Math.max(5, (card.y / dashboard.value.wall.canvas_height) * 100))}%`,
  }
}

function cardTone(card: ResearchDashboard['cards'][number], index: number) {
  if (card.sentiment === 'positive') return 'tone-green'
  if (card.sentiment === 'negative') return 'tone-pink'
  const tones = ['tone-yellow', 'tone-blue', 'tone-purple', 'tone-orange']
  return tones[index % tones.length]
}

function shortText(text: string) {
  const clean = text.replace(/\s+/g, '')
  return clean.length > 18 ? `${clean.slice(0, 18)}…` : clean
}

function rowPosition(event: ResearchTimelineEvent) {
  if (event.x == null || event.y == null) return '-'
  return `(${Math.round(event.x)}, ${Math.round(event.y)})`
}

function rowDevice(event: ResearchTimelineEvent) {
  return event.source === 'research' ? 'Web行为' : '业务接口'
}

function selectUser(userId: string | null) {
  selectedUserId.value = selectedUserId.value === userId ? '' : userId || ''
}

function showSection(section: ResearchSection) {
  activeSection.value = section
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function exportAll() {
  const blob = await api.exportResearchCsv(wallId.value)
  downloadBlob(blob, `${wallId.value}-research-timeline.csv`)
}

async function exportCardsCsv() {
  const blob = await api.exportWallCsv(wallId.value)
  downloadBlob(blob, `${wallId.value}-cards.csv`)
}

async function exportActionsCsv() {
  const blob = await api.exportWallActionsCsv(wallId.value)
  downloadBlob(blob, `${wallId.value}-actions.csv`)
}

async function exportSelectedUser() {
  if (!selectedUserId.value) return
  const blob = await api.exportResearchUserCsv(wallId.value, selectedUserId.value)
  downloadBlob(blob, `${wallId.value}-${selectedUserId.value}-research.csv`)
}

function openWallManagement() {
  router.push('/admin/walls')
}

async function archiveWall() {
  if (!window.confirm('确认结束并归档这面墙吗？归档后会从进行中列表移到已归档。')) return
  archiving.value = true
  try {
    await api.updateWall(wallId.value, { is_archived: true })
    router.push('/admin/walls')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '归档失败'
  } finally {
    archiving.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="research-page">
    <aside class="research-sidebar">
      <div class="research-brand">
        <span><BarChart3 :size="19" /></span>
        <b>反馈墙研究平台</b>
      </div>
      <nav class="research-nav">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="{ active: activeSection === item.key }"
          type="button"
          @click="showSection(item.key)"
        >
          <component :is="item.icon" :size="17" />{{ item.label }}
        </button>
      </nav>
      <div class="research-sidebar-foot">
        <button type="button" @click="router.push('/admin/walls')"><ArrowLeft :size="16" />返回工作台</button>
        <div>
          <span>{{ currentAdminName }}</span>
          <small>管理员</small>
        </div>
      </div>
    </aside>

    <section class="research-main">
      <header class="research-topbar">
        <div class="research-title-block">
          <div class="research-title-row">
            <h1>{{ dashboard?.wall.title || '研究现场' }}</h1>
            <span>进行中</span>
          </div>
          <p>
            墙ID：{{ wallId }} <i></i>
            创建时间：{{ formatTime(dashboard?.metrics.started_at || null) }} <i></i>
            当前管理员：{{ currentAdminName }}
          </p>
        </div>
        <div class="research-toolbar">
          <button class="secondary" type="button" :disabled="loading" @click="load">
            <RefreshCw :size="16" />实时刷新
          </button>
          <button class="secondary" type="button" :disabled="!dashboard" @click="exportAll">
            <Download :size="16" />导出数据
          </button>
          <button class="secondary" type="button" @click="openWallManagement"><Settings :size="16" />管理墙面</button>
          <button class="primary archive-action" type="button" :disabled="archiving" @click="archiveWall">
            <Lock :size="16" />结束并归档
          </button>
        </div>
      </header>

      <p v-if="error" class="form-error research-error">{{ error }}</p>

      <template v-if="dashboard">
        <div class="research-filterbar">
          <small>{{ sectionSummary }}</small>
          <span><ShieldCheck :size="13" />实时</span>
          <span class="research-filter-chip"><CalendarClock :size="14" />全量采集</span>
        </div>

        <section class="research-metrics">
          <article v-for="metric in metricCards" :key="metric.label" :class="['research-metric', metric.tone]">
            <span><component :is="metric.icon" :size="22" /></span>
            <div>
              <small>{{ metric.label }}</small>
              <b>{{ metric.value }}<em>{{ metric.suffix }}</em></b>
              <p>{{ metric.label === '时间跨度' ? metric.delta : `较上个时段 ${metric.delta}` }}</p>
            </div>
          </article>
        </section>

        <section v-if="activeSection === 'overview'" class="research-overview-grid">
          <article class="research-panel heatmap-panel">
            <header class="research-panel-head heatmap-head">
              <div>
                <h2>全墙注意力热力图</h2>
              </div>
              <div class="heatmap-tools">
                <span>关注度低</span>
                <i></i>
                <span>关注度高</span>
              </div>
            </header>
            <div class="heatmap-modebar">
              <div class="segmented-control">
                <button :class="{ active: heatMode === 'all' }" @click="heatMode = 'all'">全部</button>
                <button :class="{ active: heatMode === 'ui:click' }" @click="heatMode = 'ui:click'">点击</button>
                <button :class="{ active: heatMode === 'pointer:sample' }" @click="heatMode = 'pointer:sample'">鼠标</button>
                <button :class="{ active: heatMode === 'card:visible' }" @click="heatMode = 'card:visible'">曝光</button>
              </div>
            </div>
            <div class="research-map">
              <div class="research-map-grid"></div>
              <i
                v-for="point in filteredHeatPoints"
                :key="point.id"
                class="heat-point"
                :class="eventTone(point.event_type)"
                :style="pointStyle(point)"
                :title="`${eventLabel(point.event_type)} · ${point.user_name || '用户'}`"
              ></i>
              <button
                v-for="(card, index) in dashboard.cards"
                :key="card.id"
                class="research-sticky-note"
                :class="[cardTone(card, index), { selected: card.author_id === selectedUserId }]"
                :style="cardStyle(card)"
                :title="card.plain_text"
                type="button"
                @click="selectUser(card.author_id)"
              >
                <span>{{ shortText(card.plain_text) }}</span>
              </button>
              <div class="heatmap-count">便签数量：{{ dashboard.metrics.cards }}</div>
              <div class="heatmap-hint"><ArrowLeft :size="13" />坐标映射视图</div>
            </div>
          </article>

          <aside class="research-panel participant-panel">
            <header class="research-panel-head">
              <h2>参与者参与度排行</h2>
              <button class="link-button" type="button" @click="selectedUserId = ''">查看全部</button>
            </header>
            <div class="participant-table">
              <div class="participant-table-head">
                <span>排名</span>
                <span>参与者</span>
                <span>参与度得分</span>
                <span>事件数</span>
                <span>便签数</span>
                <span>反应数</span>
              </div>
              <button
                v-for="row in participationRows.slice(0, 8)"
                :key="row.user.actor_id"
                class="participant-row"
                :class="{ active: row.user.user_id === selectedUserId }"
                type="button"
                @click="selectUser(row.user.user_id)"
              >
                <span class="rank-cell" :class="`rank-${row.rank}`">{{ row.rank <= 3 ? row.rank : row.rank }}</span>
                <span class="participant-name">
                  <i>{{ row.user.user_name.slice(0, 1) }}</i>
                  {{ row.user.user_name }}
                </span>
                <span class="score-cell"><b :style="{ width: `${row.normalized}%` }"></b>{{ row.normalized }}</span>
                <span>{{ row.user.event_count }}</span>
                <span>{{ row.user.card_count }}</span>
                <span>{{ row.user.reaction_count }}</span>
              </button>
            </div>
            <footer v-if="activeUser" class="participant-detail">
              <b>{{ activeUser.user_name }} 的行为摘要</b>
              <span>{{ activeUser.card_count }} 便签 · {{ activeUser.reaction_count }} 反应 · {{ formatDuration(activeUser.active_span_seconds) }}</span>
              <button class="secondary mini" type="button" @click="exportSelectedUser">
                <Download :size="13" />导出该用户
              </button>
            </footer>
            <p v-else class="participant-note">参与度得分综合事件数、便签数、反应数计算</p>
          </aside>
        </section>

        <section v-if="activeSection === 'realtime'" class="research-live-grid">
          <article class="research-panel live-stream-panel">
            <header class="research-panel-head">
              <h2>最新事件流</h2>
              <button class="secondary mini" type="button" :disabled="loading" @click="load">
                <RefreshCw :size="13" />刷新
              </button>
            </header>
            <div class="live-event-list">
              <button
                v-for="event in latestEvents"
                :key="event.id"
                class="live-event-row"
                type="button"
                @click="selectUser(event.user_id)"
              >
                <span>{{ formatClockTime(event.created_at) }}</span>
                <i :class="eventTone(event.event_type)">{{ eventLabel(event.event_type) }}</i>
                <b>{{ event.user_name || '系统' }}</b>
                <small>{{ event.plain_text || event.target_id || event.source }}</small>
              </button>
            </div>
          </article>

          <aside class="research-panel live-side-panel">
            <header class="research-panel-head">
              <h2>最近活跃用户</h2>
            </header>
            <div class="live-user-list">
              <button
                v-for="row in recentUserRows"
                :key="row.user.actor_id"
                :class="{ active: row.user.user_id === selectedUserId }"
                type="button"
                @click="selectUser(row.user.user_id)"
              >
                <b>{{ row.user.user_name }}</b>
                <span>{{ formatTime(row.user.last_seen) }}</span>
                <small>{{ row.user.event_count }} 事件 · {{ row.user.card_count }} 便签 · {{ row.user.reaction_count }} 反应</small>
              </button>
            </div>
          </aside>

          <article class="research-panel live-card-panel">
            <header class="research-panel-head">
              <h2>最新反馈内容</h2>
            </header>
            <div class="live-card-list">
              <button
                v-for="card in latestCards"
                :key="card.id"
                class="live-card-row"
                type="button"
                @click="selectUser(card.author_id)"
              >
                <b>{{ card.author_name }}</b>
                <i :class="card.sentiment || 'unknown'">{{ card.sentiment || 'unknown' }}</i>
                <span>{{ card.reaction_count }} 反应</span>
                <small>{{ card.plain_text }}</small>
              </button>
            </div>
          </article>
        </section>

        <section v-if="activeSection === 'overview' || activeSection === 'analysis'" class="research-analysis-grid">
          <article class="research-panel trend-panel">
            <header class="research-panel-head">
              <h2>事件趋势（按分钟）</h2>
              <div class="trend-legend">
                <span v-for="series in timelineSeries" :key="series.key"><i :style="{ background: series.color }"></i>{{ series.label }}</span>
              </div>
            </header>
            <svg class="trend-chart" viewBox="0 0 640 170" role="img" aria-label="事件趋势图">
              <line x1="24" y1="142" x2="616" y2="142" />
              <line x1="24" y1="106" x2="616" y2="106" />
              <line x1="24" y1="70" x2="616" y2="70" />
              <line x1="24" y1="34" x2="616" y2="34" />
              <polyline
                v-for="series in timelineSeries"
                :key="series.key"
                :points="series.points"
                :stroke="series.color"
              />
            </svg>
          </article>

          <article class="research-panel type-panel">
            <header class="research-panel-head">
              <h2>事件类型占比</h2>
            </header>
            <div class="type-content">
              <div class="research-donut" :style="donutStyle">
                <span><b>{{ filteredTimeline.length }}</b>总事件数</span>
              </div>
              <div class="type-list">
                <span v-for="item in eventBreakdown" :key="item.key">
                  <i :style="{ background: item.color }"></i>{{ item.label }}<b>{{ item.percent }}%</b>
                </span>
              </div>
            </div>
          </article>
        </section>

        <section v-if="activeSection === 'participants'" class="research-panel participant-panel participant-panel-full">
          <header class="research-panel-head">
            <h2>参与者完整列表</h2>
            <button class="link-button" type="button" @click="selectedUserId = ''">清除筛选</button>
          </header>
          <div class="participant-table participant-table-full">
            <div class="participant-table-head">
              <span>排名</span>
              <span>参与者</span>
              <span>参与度得分</span>
              <span>事件数</span>
              <span>便签数</span>
              <span>反应数</span>
            </div>
            <button
              v-for="row in participationRows"
              :key="row.user.actor_id"
              class="participant-row"
              :class="{ active: row.user.user_id === selectedUserId }"
              type="button"
              @click="selectUser(row.user.user_id)"
            >
              <span class="rank-cell" :class="`rank-${row.rank}`">{{ row.rank }}</span>
              <span class="participant-name">
                <i>{{ row.user.user_name.slice(0, 1) }}</i>
                {{ row.user.user_name }}
              </span>
              <span class="score-cell"><b :style="{ width: `${row.normalized}%` }"></b>{{ row.normalized }}</span>
              <span>{{ row.user.event_count }}</span>
              <span>{{ row.user.card_count }}</span>
              <span>{{ row.user.reaction_count }}</span>
            </button>
          </div>
          <footer v-if="activeUser" class="participant-detail">
            <b>{{ activeUser.user_name }} 的行为摘要</b>
            <span>
              {{ activeUser.card_count }} 便签 · {{ activeUser.reaction_count }} 反应 ·
              {{ activeUser.research_event_count }} 前端行为 · {{ formatDuration(activeUser.active_span_seconds) }}
            </span>
            <button class="secondary mini" type="button" @click="exportSelectedUser">
              <Download :size="13" />导出该用户
            </button>
          </footer>
        </section>

        <section v-if="activeSection === 'content'" class="research-panel event-table-panel">
          <header class="research-panel-head">
            <h2>反馈内容列表（{{ contentRows.length }} 条）</h2>
            <label class="research-search">
              <Search :size="15" />
              <input v-model="contentQuery" placeholder="筛选作者、内容或情绪" />
            </label>
          </header>
          <div class="research-card-table">
            <div class="research-card-table-head">
              <span>作者</span>
              <span>情绪</span>
              <span>反应数</span>
              <span>创建时间</span>
              <span>反馈内容</span>
            </div>
            <button
              v-for="card in contentRows"
              :key="card.id"
              class="research-card-table-row"
              :class="{ active: card.author_id === selectedUserId }"
              type="button"
              @click="selectUser(card.author_id)"
            >
              <b>{{ card.author_name }}</b>
              <i :class="card.sentiment || 'unknown'">{{ card.sentiment || 'unknown' }}</i>
              <span>{{ card.reaction_count }}</span>
              <span>{{ formatClockTime(card.created_at) }}</span>
              <small>{{ card.plain_text }}</small>
            </button>
          </div>
        </section>

        <section v-if="activeSection === 'exports'" class="research-export-grid">
          <article class="research-panel export-panel">
            <header class="research-panel-head">
              <h2>可导出数据集</h2>
            </header>
            <div class="export-actions">
              <button type="button" @click="exportAll">
                <Download :size="16" />
                <span><b>科研行为 CSV</b><small>包含鼠标、点击、曝光、滚动、会话等事件</small></span>
              </button>
              <button type="button" @click="exportCardsCsv">
                <Download :size="16" />
                <span><b>反馈内容 CSV</b><small>包含便签文本、作者、情绪、反应统计</small></span>
              </button>
              <button type="button" @click="exportActionsCsv">
                <Download :size="16" />
                <span><b>业务操作 CSV</b><small>包含创建、编辑、移动、反应、摘要等操作日志</small></span>
              </button>
              <button type="button" :disabled="!selectedUserId" @click="exportSelectedUser">
                <Download :size="16" />
                <span><b>当前用户 CSV</b><small>{{ activeUser ? activeUser.user_name : '先在参与者列表或热力图中选择用户' }}</small></span>
              </button>
            </div>
            <div class="export-dictionaries">
              <details v-for="schema in exportSchemas" :key="schema.key" :open="schema.key === 'research'">
                <summary>{{ schema.title }}表头说明</summary>
                <p>{{ schema.note }}</p>
                <div class="export-field-table">
                  <div v-for="[field, meaning] in schema.fields" :key="field">
                    <b>{{ field }}</b>
                    <span>{{ meaning }}</span>
                  </div>
                </div>
              </details>
            </div>
          </article>
          <article class="research-panel export-panel">
            <header class="research-panel-head">
              <h2>当前筛选状态</h2>
            </header>
            <dl class="export-state">
              <div><dt>墙面</dt><dd>{{ dashboard.wall.title }}</dd></div>
              <div><dt>用户筛选</dt><dd>{{ activeUser?.user_name || '全部用户' }}</dd></div>
              <div><dt>行为事件</dt><dd>{{ dashboard.metrics.behavior_events }} 条</dd></div>
              <div><dt>业务事件</dt><dd>{{ dashboard.metrics.action_events }} 条</dd></div>
              <div><dt>便签内容</dt><dd>{{ dashboard.metrics.cards }} 条</dd></div>
              <div><dt>反应记录</dt><dd>{{ dashboard.metrics.reactions }} 次</dd></div>
            </dl>
          </article>
        </section>

        <section v-if="activeSection === 'overview' || activeSection === 'events'" class="research-panel event-table-panel">
          <header class="research-panel-head">
            <h2>{{ eventTableTitle }}</h2>
            <label class="research-search">
              <Search :size="15" />
              <input v-model="eventQuery" placeholder="筛选用户、事件或文本" />
            </label>
          </header>
          <div class="research-table">
            <div class="research-table-head">
              <span>时间</span>
              <span>事件类型</span>
              <span>参与者</span>
              <span>事件内容</span>
              <span>目标便签</span>
              <span>位置</span>
              <span>来源</span>
            </div>
            <div v-for="event in displayedRows" :key="event.id" class="research-table-row">
              <span>{{ formatClockTime(event.created_at) }}</span>
              <i :class="eventTone(event.event_type)">{{ eventLabel(event.event_type) }}</i>
              <b>{{ event.user_name || '系统' }}</b>
              <small>{{ event.plain_text || event.target_id || event.source }}</small>
              <span>{{ event.target_id || '-' }}</span>
              <span>{{ rowPosition(event) }}</span>
              <span>{{ rowDevice(event) }}</span>
            </div>
          </div>
        </section>
      </template>

      <section v-else-if="loading" class="research-loading">
        <RefreshCw :size="18" />正在读取科研行为数据
      </section>

      <LoginModal v-if="showLogin" @close="closeLogin" />
    </section>
  </main>
</template>
