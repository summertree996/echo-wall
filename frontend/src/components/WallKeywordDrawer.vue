<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Cloud, Maximize2, Minimize2, RefreshCw, X } from '@lucide/vue'
import WordCloud from 'wordcloud'
import type { Card, Sentiment } from '../types'
import { buildKeywordCloud, type KeywordCloudItem, type KeywordCloudModel, type KeywordFilter } from '../utils/keywordCloud'

type DrawerSize = 'drawer' | 'wide' | 'focus'

const props = withDefaults(defineProps<{
  open?: boolean
  cards: Card[]
  size?: DrawerSize
}>(), {
  open: true,
  size: 'wide',
})

const emit = defineEmits<{
  close: []
  toggleSize: []
}>()

const activeFilter = ref<KeywordFilter>('all')
const activeWord = ref('')
const loading = ref(false)
const model = ref<KeywordCloudModel>({ totalCards: 0, totalTerms: 0, items: [] })
const canvasRef = ref<HTMLCanvasElement | null>(null)
const cloudRef = ref<HTMLElement | null>(null)
let refreshTimer: number | undefined

const filters: Array<{ key: KeywordFilter; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'positive', label: '正向' },
  { key: 'neutral', label: '中性' },
  { key: 'negative', label: '关注' },
]

const activeItem = computed(() => model.value.items.find((item) => item.text === activeWord.value) || model.value.items[0] || null)
const relatedComments = computed(() => activeItem.value?.comments || [])
const topItems = computed(() => model.value.items.slice(0, 16))
const cloudTitle = computed(() => {
  if (!model.value.totalCards) return '关键词云'
  return `${model.value.totalCards} 条反馈 · ${model.value.totalTerms} 个关键词`
})
const maxWeight = computed(() => model.value.items[0]?.weight || 1)

watch(() => props.open, (open) => {
  if (open) scheduleRefresh()
})

watch(() => activeFilter.value, () => {
  activeWord.value = ''
  scheduleRefresh()
})

watch(() => props.cards.map((card) => `${card.id}:${card.updated_at}:${card.sentiment}:${card.topic_labels.join(',')}:${card.reaction_counts.like}:${card.reaction_counts.dislike}:${card.reaction_counts.question}`).join('|'), () => {
  if (props.open) scheduleRefresh(180)
})

function scheduleRefresh(delay = 60) {
  if (!props.open) return
  if (refreshTimer) window.clearTimeout(refreshTimer)
  loading.value = true
  refreshTimer = window.setTimeout(async () => {
    model.value = buildKeywordCloud(props.cards, activeFilter.value)
    if (!activeWord.value || !model.value.items.some((item) => item.text === activeWord.value)) {
      activeWord.value = model.value.items[0]?.text || ''
    }
    loading.value = false
    await nextTick()
    renderCloud()
  }, delay)
}

function renderCloud() {
  const canvas = canvasRef.value
  const host = cloudRef.value
  if (!canvas || !host || !model.value.items.length) return
  const width = Math.max(520, Math.round(host.clientWidth))
  const height = Math.max(390, Math.round(host.clientHeight))
  canvas.width = width
  canvas.height = height
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  WordCloud.stop?.()
  WordCloud(canvas, {
    list: model.value.items.map((item) => [item.text, wordSize(item), item]),
    gridSize: Math.max(8, Math.round(width / 92)),
    weightFactor: 1,
    fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: '800',
    backgroundColor: 'transparent',
    rotateRatio: 0,
    shape: 'square',
    ellipticity: 0.72,
    color: (word) => toneColor(model.value.items.find((item) => item.text === word)?.sentiment || 'mixed'),
    click: (item) => {
      if (item?.[0]) activeWord.value = item[0]
    },
  })
}

function wordSize(item: KeywordCloudItem) {
  return Math.round(16 + (item.weight / maxWeight.value) * 44)
}

function setFilter(filter: KeywordFilter) {
  activeFilter.value = filter
}

function selectWord(word: string) {
  activeWord.value = word
}

function toneClass(sentiment: Sentiment | 'mixed' | null) {
  return `tone-${sentiment || 'mixed'}`
}

function toneColor(sentiment: Sentiment | 'mixed') {
  if (sentiment === 'positive') return '#14945d'
  if (sentiment === 'negative') return '#d14b42'
  if (sentiment === 'neutral') return '#687386'
  return '#5b5bf0'
}

function sentimentLabel(sentiment: Sentiment | null) {
  if (sentiment === 'positive') return '正向'
  if (sentiment === 'negative') return '关注'
  if (sentiment === 'neutral') return '中性'
  return '未标注'
}

onMounted(() => {
  scheduleRefresh()
  window.addEventListener('resize', renderCloud)
})

onUnmounted(() => {
  if (refreshTimer) window.clearTimeout(refreshTimer)
  window.removeEventListener('resize', renderCloud)
  WordCloud.stop?.()
})
</script>

<template>
  <aside v-if="open" class="keyword-drawer" :class="`size-${size}`">
    <header class="keyword-head">
      <div>
        <span class="keyword-kicker"><Cloud :size="15" />本地词频</span>
        <h2>关键词云</h2>
        <p>{{ cloudTitle }}</p>
      </div>
      <div class="keyword-actions">
        <span class="keyword-status">{{ loading ? '更新中' : '已更新' }}</span>
        <button class="keyword-icon" type="button" :title="size === 'focus' ? '收起' : '展开'" @click="emit('toggleSize')">
          <Minimize2 v-if="size === 'focus'" :size="18" />
          <Maximize2 v-else :size="18" />
        </button>
        <button class="keyword-icon" type="button" title="刷新" @click="scheduleRefresh(0)"><RefreshCw :size="18" /></button>
        <button class="keyword-icon" type="button" title="关闭" @click="emit('close')"><X :size="18" /></button>
      </div>
    </header>

    <nav class="keyword-tabs" aria-label="关键词筛选">
      <button
        v-for="filter in filters"
        :key="filter.key"
        type="button"
        :class="{ active: activeFilter === filter.key }"
        @click="setFilter(filter.key)"
      >
        {{ filter.label }}
      </button>
    </nav>

    <main class="keyword-body">
      <section class="cloud-panel">
        <div ref="cloudRef" class="cloud-canvas-wrap" :class="{ empty: !model.items.length }">
          <canvas v-show="model.items.length" ref="canvasRef" aria-label="关键词云"></canvas>
          <div v-if="!model.items.length" class="keyword-empty">
            <Cloud :size="24" />
            <b>{{ loading ? '更新中' : '暂无关键词' }}</b>
          </div>
        </div>
      </section>

      <aside class="keyword-side">
        <section class="keyword-metrics">
          <article>
            <b>{{ model.totalTerms }}</b>
            <span>关键词</span>
          </article>
          <article>
            <b>{{ model.totalCards }}</b>
            <span>反馈</span>
          </article>
          <article>
            <b>{{ activeItem?.cardCount || 0 }}</b>
            <span>覆盖</span>
          </article>
        </section>

        <section class="keyword-list">
          <div class="side-head">
            <h3>高频词</h3>
            <span>{{ topItems.length }} 个</span>
          </div>
          <button
            v-for="item in topItems"
            :key="item.text"
            type="button"
            :class="{ active: activeWord === item.text }"
            @click="selectWord(item.text)"
          >
            <b>{{ item.text }}</b>
            <span :class="toneClass(item.sentiment)">{{ item.cardCount }} 条</span>
          </button>
        </section>

        <section class="keyword-voices">
          <div class="side-head">
            <h3>{{ activeItem?.text || '相关声音' }}</h3>
            <span>{{ relatedComments.length }} 条</span>
          </div>
          <article v-for="comment in relatedComments" :key="comment.id" class="voice-row">
            <p>{{ comment.text }}</p>
            <footer>
              <span>{{ comment.authorName }}</span>
              <span>{{ sentimentLabel(comment.sentiment) }}</span>
              <span>{{ comment.reactionCount }} 互动</span>
            </footer>
          </article>
        </section>
      </aside>
    </main>
  </aside>
</template>

<style scoped>
.keyword-drawer {
  position: fixed;
  inset: 0 0 0 auto;
  z-index: 985;
  width: min(1040px, calc(100vw - 96px));
  min-width: 680px;
  height: 100vh;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  background: rgba(255,255,255,0.98);
  border-left: 1px solid #e6e9ef;
  box-shadow: -28px 0 60px rgba(20,22,32,0.18);
  color: #222631;
}
.keyword-drawer.size-drawer { width: min(760px, calc(100vw - 128px)); min-width: 560px; }
.keyword-drawer.size-wide { width: min(1040px, calc(100vw - 96px)); }
.keyword-drawer.size-focus { width: min(1240px, calc(100vw - 56px)); }
.keyword-head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: start;
  padding: 28px 30px 18px;
  border-bottom: 1px solid #eef0f4;
}
.keyword-kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #5b5bf0;
  font-size: 13px;
  font-weight: 900;
}
.keyword-head h2 {
  margin: 9px 0 7px;
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: 0;
}
.keyword-head p {
  margin: 0;
  color: #7a808d;
  font-size: 14px;
}
.keyword-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.keyword-status {
  border-radius: 999px;
  padding: 6px 10px;
  background: #f0f1ff;
  color: #5b5bf0;
  font-size: 12px;
  font-weight: 900;
}
.keyword-icon {
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
.keyword-tabs {
  display: flex;
  gap: 6px;
  padding: 12px 30px;
  border-bottom: 1px solid #eef0f4;
}
.keyword-tabs button {
  min-height: 36px;
  border: none;
  border-radius: 999px;
  padding: 0 14px;
  background: transparent;
  color: #69707d;
  font-weight: 850;
  cursor: pointer;
}
.keyword-tabs button.active {
  background: #171922;
  color: #fff;
}
.keyword-body {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 18px;
  padding: 18px 30px 24px;
  overflow: hidden;
}
.cloud-panel,
.keyword-side section {
  border: 1px solid #edf0f4;
  border-radius: 8px;
  background: #fff;
}
.cloud-panel {
  min-width: 0;
  min-height: 0;
  padding: 14px;
}
.cloud-canvas-wrap {
  position: relative;
  min-height: 520px;
  height: 100%;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 7px;
  background:
    linear-gradient(rgba(246,248,251,0.74) 1px, transparent 1px),
    linear-gradient(90deg, rgba(246,248,251,0.74) 1px, transparent 1px);
  background-size: 28px 28px;
}
.cloud-canvas-wrap canvas {
  max-width: 100%;
  cursor: pointer;
}
.keyword-empty {
  display: grid;
  place-items: center;
  gap: 8px;
  color: #8b909c;
}
.keyword-empty b {
  color: #222631;
}
.keyword-side {
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  gap: 12px;
  overflow: hidden;
}
.keyword-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
}
.keyword-metrics article {
  padding: 13px;
}
.keyword-metrics article + article {
  border-left: 1px solid #edf0f4;
}
.keyword-metrics b {
  display: block;
  font-size: 23px;
  line-height: 1;
}
.keyword-metrics span {
  display: block;
  margin-top: 7px;
  color: #7a808d;
  font-size: 12px;
  font-weight: 850;
}
.keyword-list,
.keyword-voices {
  min-height: 0;
  padding: 13px;
}
.side-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.side-head h3 {
  margin: 0;
  font-size: 15px;
}
.side-head span {
  color: #8b909c;
  font-size: 12px;
  font-weight: 900;
}
.keyword-list {
  display: grid;
  gap: 7px;
}
.keyword-list button {
  min-height: 34px;
  border: none;
  border-radius: 7px;
  padding: 7px 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #f8f9fb;
  color: #313743;
  cursor: pointer;
  text-align: left;
}
.keyword-list button.active {
  background: #171922;
  color: #fff;
}
.keyword-list b {
  font-size: 13px;
}
.keyword-list span {
  border-radius: 999px;
  padding: 4px 7px;
  font-size: 11px;
  font-weight: 900;
}
.tone-positive { background: #e1f6eb; color: #148650; }
.tone-neutral { background: #edf1f5; color: #64707f; }
.tone-negative { background: #ffe4e1; color: #c84339; }
.tone-mixed { background: #eeeefe; color: #5b5bf0; }
.keyword-list button.active span {
  background: rgba(255,255,255,0.15);
  color: #fff;
}
.keyword-voices {
  overflow: auto;
}
.voice-row {
  border-radius: 7px;
  padding: 10px;
  background: #f8f9fb;
}
.voice-row + .voice-row {
  margin-top: 8px;
}
.voice-row p {
  margin: 0;
  color: #343945;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.voice-row footer {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #8b909c;
  font-size: 12px;
  font-weight: 800;
}
@media (max-width: 900px) {
  .keyword-drawer,
  .keyword-drawer.size-drawer,
  .keyword-drawer.size-wide,
  .keyword-drawer.size-focus {
    width: 100vw;
    min-width: 0;
  }
  .keyword-head,
  .keyword-tabs,
  .keyword-body {
    padding-left: 18px;
    padding-right: 18px;
  }
  .keyword-body {
    grid-template-columns: 1fr;
    overflow: auto;
  }
  .cloud-canvas-wrap {
    min-height: 360px;
  }
}
</style>
