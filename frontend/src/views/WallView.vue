<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CardDetailModal from '../components/CardDetailModal.vue'
import LoginModal from '../components/LoginModal.vue'
import OnlineRail from '../components/OnlineRail.vue'
import PresentationOverlay from '../components/PresentationOverlay.vue'
import StickyCard from '../components/StickyCard.vue'
import WallAnalysisDrawer from '../components/WallAnalysisDrawer.vue'
import WallAccessModal from '../components/WallAccessModal.vue'
import WallCreateModal from '../components/WallCreateModal.vue'
import WallEmptyState from '../components/WallEmptyState.vue'
import WallModeBanners from '../components/WallModeBanners.vue'
import WallSummaryModal from '../components/WallSummaryModal.vue'
import WallToolDock from '../components/WallToolDock.vue'
import WallTopbar from '../components/WallTopbar.vue'
import { useCardDetail } from '../composables/useCardDetail'
import { useCardCreation } from '../composables/useCardCreation'
import { useCardDragging } from '../composables/useCardDragging'
import { usePresentationCarousel } from '../composables/usePresentationCarousel'
import { useResearchTelemetry } from '../composables/useResearchTelemetry'
import { useWallSummary } from '../composables/useWallSummary'
import { useAuthStore } from '../stores/auth'
import { useWallStore } from '../stores/wall'
import { buildOrganizeGuides, buildTopicBuckets, guideCountText, guideToneClass, layoutSentiment, layoutTopic, type ViewMode } from '../utils/organizeLayout'
import { buildWallAnalysis, type AnalysisTab } from '../utils/wallAnalysis'
import type { Card, ReactionType } from '../types'

type Tool = 'add' | 'react' | 'drag'
type AnalysisDrawerSize = 'drawer' | 'wide' | 'focus'

const WallKeywordDrawer = defineAsyncComponent(() => import('../components/WallKeywordDrawer.vue'))

const route = useRoute()
const auth = useAuthStore()
const wallStore = useWallStore()
const tool = ref<Tool>('react')
const viewMode = ref<ViewMode>('free')
const organizedCardIds = ref<Set<string> | null>(null)
const showLogin = ref(false)
const wallPassword = ref('')
const wallPasswordError = ref('')
const wallPasswordLoading = ref(false)
const stageRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLElement | null>(null)
const unseenNewCards = ref<Card[]>([])
const locallyRaisedCardId = ref<string | null>(null)
const showAnalysisDrawer = ref(false)
const analysisTab = ref<AnalysisTab>('overview')
const analysisDrawerSize = ref<AnalysisDrawerSize>('wide')
const showKeywordDrawer = ref(false)
const keywordDrawerSize = ref<AnalysisDrawerSize>('wide')

const wallId = computed(() => String(route.params.wallId))
const research = useResearchTelemetry({
  wallId: () => wallId.value,
  enabled: () => Boolean(wallStore.wall && !wallStore.requiresLogin && !wallStore.requiresPassword),
  stageRef,
  canvasRef,
  viewMode: () => viewMode.value,
  tool: () => tool.value,
  cardCount: () => wallStore.cards.length,
  send: (events) => wallStore.trackResearchEvents(events),
})
const {
  showSummary,
  summary,
  summaryLoading,
  summaryError,
  summaryDiff,
  summaryDiffLoading,
  summaryDiffError,
  summaryHistory,
  summaryHistoryLoading,
  openSummary,
  openHistoricalSummary,
  loadSummaryDiff,
} = useWallSummary(() => wallId.value, () => Boolean(auth.user?.is_admin))
const {
  showPresentation,
  presentationCards,
  currentPresentationCard,
  presentationIndex,
  startPresentation,
  stopPresentation,
} = usePresentationCarousel(() => wallStore.cards, () => spotlightCard.value)
const {
  selectedCard,
  canEditSelected,
  editingSelected,
  detailSaving,
  detailError,
  openDetail,
  closeDetail,
  submitSelectedEdit,
  deleteSelectedCard,
} = useCardDetail(
  () => wallStore.cards,
  () => auth.user,
  (cardId, payload) => wallStore.updateCard(cardId, payload),
  (cardId) => wallStore.deleteCard(cardId),
)
const isOrganized = computed(() => viewMode.value !== 'free')
const spotlightCard = computed(() => wallStore.cards.find((card) => card.id === wallStore.spotlightCardId) || null)
const isSpotlightActive = computed(() => Boolean(wallStore.spotlightCardId))
const isWallLocked = computed(() => Boolean(wallStore.wall?.is_locked))
const dockPaused = computed(() => isOrganized.value || isSpotlightActive.value)
const interactionPaused = computed(() => dockPaused.value || isWallLocked.value)
const disabledDockTools = computed<Tool[]>(() => isWallLocked.value ? ['add', 'drag'] : [])
const {
  showEditor,
  placementPreview,
  snapGhost,
  placementHint,
  highlightedCardId,
  updatePlacementPreview,
  hidePlacementPreview,
  openEditor,
  submitCard,
  closeEditor,
  highlightCard,
  disposeCardCreation,
} = useCardCreation({
  tool,
  interactionPaused,
  canvasRef,
  user: () => auth.user,
  requiresPassword: () => wallStore.requiresPassword,
  cards: () => wallStore.cards,
  placeholders: () => wallStore.placeholders,
  requestLogin: () => {
    showLogin.value = true
  },
  createPlaceholder: (payload) => wallStore.createPlaceholder(payload),
  renewPlaceholder: (placeholderId) => wallStore.renewPlaceholder(placeholderId),
  releasePlaceholder: (placeholderId) => wallStore.releasePlaceholder(placeholderId),
  createCard: (payload) => wallStore.createCard(payload),
})
const {
  drag,
  startDrag,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
  positionFor,
} = useCardDragging({
  tool,
  interactionPaused,
  canvasRef,
  user: () => auth.user,
  dragPreview: () => wallStore.dragPreview,
  sendTransient: (cardId, x, y) => wallStore.sendTransient(cardId, x, y),
  moveCard: (cardId, x, y, canvasWidth) => wallStore.moveCard(cardId, x, y, canvasWidth),
})
const organizedCards = computed(() => {
  const ids = organizedCardIds.value
  if (!ids) return wallStore.sortedCards
  return wallStore.sortedCards.filter((card) => ids.has(card.id))
})
const organizedPendingCount = computed(() => {
  const ids = organizedCardIds.value
  if (!isOrganized.value || !ids) return 0
  return wallStore.cards.filter((card) => !ids.has(card.id)).length
})
const topicBuckets = computed(() => buildTopicBuckets(organizedCards.value))
const organizeGuides = computed(() => buildOrganizeGuides(viewMode.value, organizedCards.value, topicBuckets.value))
const connectionLabel = computed(() => {
  if (wallStore.requiresPassword) return '需要访问口令'
  if (wallStore.requiresLogin) return '登录后连接'
  return wallStore.connected ? '实时已连接' : '正在重连'
})
const cardsForRender = computed(() => {
  if (viewMode.value === 'sentiment') return layoutSentiment(organizedCards.value)
  if (viewMode.value === 'topic') return layoutTopic(organizedCards.value, topicBuckets.value)
  return wallStore.sortedCards.map((card) => ({ card, x: card.x, y: card.y }))
})
const ownCardCount = computed(() => wallStore.cards.filter((card) => card.author_id === auth.user?.id).length)
const canBreatheCards = computed(() => (
  viewMode.value === 'free' &&
  !isSpotlightActive.value &&
  !showPresentation.value &&
  !showEditor.value &&
  !drag.value &&
  !wallStore.dragPreview &&
  !placementPreview.visible &&
  !snapGhost.visible
))

function cardSize(card: Card) {
  return {
    width: Math.max(card.width || 0, 250),
    height: Math.max(card.height || 0, 170),
  }
}

function overlaps(a: Card, b: Card) {
  if (a.id === b.id) return true
  const aSize = cardSize(a)
  const bSize = cardSize(b)
  const xLimit = (aSize.width + bSize.width) * 0.5
  const yLimit = (aSize.height + bSize.height) * 0.5
  return Math.abs(a.x - b.x) < xLimit && Math.abs(a.y - b.y) < yLimit
}

function raiseCard(cardId: string) {
  if (isOrganized.value) return
  locallyRaisedCardId.value = cardId
  research.track('card:raise', { targetType: 'card', targetId: cardId })
}

function cycleLocalStack(card: Card, event: WheelEvent) {
  if (isOrganized.value) return
  const stack = wallStore.sortedCards.filter((candidate) => overlaps(card, candidate)).sort((a, b) => a.z_index - b.z_index)
  if (stack.length <= 1) {
    raiseCard(card.id)
    return
  }
  const anchorId = locallyRaisedCardId.value && stack.some((item) => item.id === locallyRaisedCardId.value)
    ? locallyRaisedCardId.value
    : card.id
  const currentIndex = Math.max(0, stack.findIndex((item) => item.id === anchorId))
  const direction = event.deltaY >= 0 ? 1 : -1
  const next = stack[(currentIndex + direction + stack.length) % stack.length]
  locallyRaisedCardId.value = next.id
  research.track('card:stack_cycle', {
    targetType: 'card',
    targetId: next.id,
    payload: { stack_size: stack.length, direction },
  })
}

function cardElement(cardId: string) {
  return document.querySelector<HTMLElement>(`[data-card-id="${cardId}"]`)
}

function isCardVisible(cardId: string) {
  const el = cardElement(cardId)
  if (!el) return false
  const rect = el.getBoundingClientRect()
  return rect.bottom > 112 && rect.top < window.innerHeight - 48
}

function addNewCardNotice(card: Card) {
  if (unseenNewCards.value.some((item) => item.id === card.id)) return
  unseenNewCards.value.push(card)
}

function clearVisibleNewCardNotices() {
  if (isOrganized.value || isSpotlightActive.value || !unseenNewCards.value.length) return
  unseenNewCards.value = unseenNewCards.value.filter((card) => !isCardVisible(card.id))
}

function updatePlacementPreviewOnCanvas(event: PointerEvent | MouseEvent) {
  const target = event.target
  if (target instanceof Element && target.closest('.sticky-card, .placeholder-card, .organize-guide')) {
    hidePlacementPreview()
    return
  }
  updatePlacementPreview(event)
}

async function revealNewCards() {
  const target = unseenNewCards.value[unseenNewCards.value.length - 1]
  unseenNewCards.value = []
  if (!target) return
  if (isOrganized.value) exitOrganize()
  await nextTick()
  await highlightCard(target)
}

async function load() {
  try {
    await auth.refreshSession()
    const snapshot = await wallStore.load(wallId.value)
    await nextTick()
    if (!snapshot.requires_login && !snapshot.requires_password) {
      stageRef.value?.scrollTo({ top: 0, left: 0 })
    }
    showLogin.value = Boolean(snapshot.requires_login)
    research.track('wall:view', {
      targetType: 'wall',
      payload: {
        requires_login: Boolean(snapshot.requires_login),
        requires_password: Boolean(snapshot.requires_password),
      },
    })
  } catch {
    showLogin.value = !auth.user
  }
}

async function logout() {
  await auth.logout()
  await load()
}

async function revealOwnCards() {
  const target = wallStore.cards
    .filter((card) => card.author_id === auth.user?.id)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
  if (!target) return
  if (isOrganized.value) exitOrganize()
  await nextTick()
  research.track('card:locate_own_latest', { targetType: 'card', targetId: target.id })
  await highlightCard(target)
}

async function locateCardFromRail(cardId: string) {
  const target = wallStore.cards.find((card) => card.id === cardId)
  if (!target) return
  if (isOrganized.value) exitOrganize()
  locallyRaisedCardId.value = target.id
  await nextTick()
  research.track('card:locate_from_rail', { targetType: 'card', targetId: target.id })
  await highlightCard(target)
}

function openAnalysis(tab: AnalysisTab) {
  if (!auth.user?.is_admin) return
  showKeywordDrawer.value = false
  analysisTab.value = tab
  analysisDrawerSize.value = tab === 'summary' ? 'focus' : 'wide'
  showAnalysisDrawer.value = true
  research.track('wall:analysis_open', {
    targetType: 'wall',
    payload: { tab },
  })
  if (tab === 'summary' && !summary.value) void refreshAnalysisSummary(false)
}

function openKeywordCloud() {
  if (!auth.user?.is_admin) return
  showAnalysisDrawer.value = false
  keywordDrawerSize.value = 'wide'
  showKeywordDrawer.value = true
  research.track('wall:keyword_cloud_open', { targetType: 'wall' })
}

async function refreshAnalysisSummary(refresh = true) {
  if (!auth.user?.is_admin) return
  await openSummary(refresh, { visible: false })
}

function focusAnalysisCards(payload: { type: 'sentiment' | 'topic' | 'issue'; key: string; cardIds: string[] }) {
  research.track('wall:analysis_focus', {
    targetType: 'wall',
    payload: { type: payload.type, key: payload.key, count: payload.cardIds.length },
  })
}

function toggleAnalysisDrawerSize() {
  analysisDrawerSize.value = analysisDrawerSize.value === 'focus' ? 'wide' : 'focus'
}

function toggleKeywordDrawerSize() {
  keywordDrawerSize.value = keywordDrawerSize.value === 'focus' ? 'wide' : 'focus'
}

function exportAnalysisReport() {
  const model = buildWallAnalysis(wallStore.cards, summary.value)
  const title = wallStore.wall?.title || '反馈墙'
  const lines = [
    `# ${title} AI 分析`,
    '',
    model.headline,
    '',
    `反馈：${model.cardCount}`,
    `互动：${model.reactionCount}`,
    `主题：${model.topicGroups.length}`,
    '',
    '## 情绪',
    ...model.sentimentGroups.map((group) => `- ${group.label}：${group.count} 条，${group.percent}%`),
    '',
    '## 核心议题',
    ...model.overviewIssues.flatMap((issue) => [
      `### ${issue.title}`,
      issue.body,
      ...issue.comments.map((comment) => `- ${comment.text}`),
      '',
    ]),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeFilePart(title)}-ai-analysis.md`
  link.click()
  URL.revokeObjectURL(url)
  research.track('wall:analysis_export', { targetType: 'wall' })
}

function safeFilePart(value: string) {
  return value.trim().replace(/[\\/:*?"<>|]/g, '-').slice(0, 40) || 'wall'
}

async function submitWallPassword() {
  if (!wallPassword.value.trim()) return
  wallPasswordLoading.value = true
  wallPasswordError.value = ''
  try {
    await wallStore.unlockWall(wallId.value, wallPassword.value.trim())
    wallPassword.value = ''
  } catch (err) {
    wallPasswordError.value = err instanceof Error ? err.message : '口令校验失败'
  } finally {
    wallPasswordLoading.value = false
  }
}

function react(card: Card, reaction: ReactionType) {
  if (!auth.user) {
    showLogin.value = true
    return
  }
  research.track('card:react_intent', {
    targetType: 'card',
    targetId: card.id,
    payload: { reaction },
  })
  wallStore.react(card.id, reaction)
}

function openCardDetail(card: Card) {
  research.track('card:detail_open', { targetType: 'card', targetId: card.id })
  openDetail(card)
}

async function setSpotlight(cardId: string | null) {
  if (!auth.user?.is_admin) return
  research.track('wall:spotlight_intent', { targetType: cardId ? 'card' : 'wall', targetId: cardId })
  await wallStore.setSpotlight(cardId)
  if (cardId) closeDetail()
}

async function toggleWallLock() {
  if (!auth.user?.is_admin || !wallStore.wall) return
  research.track('wall:lock_toggle_intent', {
    targetType: 'wall',
    payload: { next_locked: !wallStore.wall.is_locked },
  })
  await wallStore.updateWall({ is_locked: !wallStore.wall.is_locked })
}

function isOwnPlaceholder(userId: string) {
  return auth.user?.id === userId
}

function exitOrganize() {
  research.track('wall:organize_exit', { targetType: 'wall', payload: { mode: viewMode.value } })
  viewMode.value = 'free'
  organizedCardIds.value = null
}

onMounted(load)
watch(() => wallStore.spotlightCardId, async (cardId) => {
  if (!cardId) return
  await nextTick()
  document.querySelector<HTMLElement>(`[data-card-id="${cardId}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
})
watch(() => wallStore.lastCreatedCard, async (card) => {
  if (!card || card.author_id === auth.user?.id) return
  await nextTick()
  if (isOrganized.value || isSpotlightActive.value || !isCardVisible(card.id)) {
    addNewCardNotice(card)
    return
  }
  await highlightCard(card, { scroll: false, duration: 1800 })
})
watch(() => auth.user?.is_admin, (isAdmin) => {
  if (!isAdmin && isOrganized.value) exitOrganize()
})
watch(isWallLocked, (locked) => {
  if (locked && tool.value !== 'react') tool.value = 'react'
})
watch(tool, (nextTool, previousTool) => {
  research.track('tool:change', {
    targetType: 'wall',
    payload: { from: previousTool, to: nextTool },
  })
})
onUnmounted(() => {
  void research.flush()
  disposeCardCreation()
  stopPresentation()
  wallStore.disconnect()
})
</script>

<template>
  <main class="wall-page" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerCancel">
    <OnlineRail
      :users="wallStore.onlineUsers"
      :anonymous="wallStore.wall?.is_anonymous || false"
      :current-user="auth.user"
      :is-admin="auth.user?.is_admin || false"
      :own-card-count="ownCardCount"
      :cards="wallStore.cards"
      :connected="wallStore.connected"
      :wall-owner-id="wallStore.wall?.owner_id || null"
      @login="showLogin = true"
      @logout="logout"
      @show-mine="revealOwnCards"
      @locate-card="locateCardFromRail"
    />

    <section ref="stageRef" class="wall-stage" @scroll.passive="clearVisibleNewCardNotices">
      <WallTopbar
        :title="wallStore.wall?.title"
        :description="wallStore.wall?.description"
        :connected="wallStore.connected"
        :connection-label="connectionLabel"
        :view-mode="viewMode"
        :is-admin="auth.user?.is_admin || false"
        :logged-in="Boolean(auth.user)"
        :summary-loading="summaryLoading"
        :card-count="wallStore.cards.length"
        :is-locked="isWallLocked"
        @organize="openAnalysis('overview')"
        @keywords="openKeywordCloud"
        @toggle-lock="toggleWallLock"
        @presentation="startPresentation"
        @summary="openAnalysis('summary')"
        @login="showLogin = true"
      />

      <WallModeBanners
        :view-mode="viewMode"
        :organized-pending-count="organizedPendingCount"
        :spotlight-text="spotlightCard?.plain_text"
        :can-cancel-spotlight="auth.user?.is_admin || false"
        @exit-organize="exitOrganize"
        @clear-spotlight="setSpotlight(null)"
      />

      <section
        ref="canvasRef"
        class="canvas"
        :class="{ 'spotlight-active': isSpotlightActive }"
        :style="{ height: `${wallStore.wall?.canvas_height || 2400}px` }"
        @click.self="openEditor"
        @pointermove="updatePlacementPreviewOnCanvas"
        @mousemove="updatePlacementPreviewOnCanvas"
        @pointerleave="hidePlacementPreview"
      >
        <div v-if="placementHint" class="placement-hint">{{ placementHint }}</div>
        <button v-if="unseenNewCards.length" class="new-card-notice" type="button" @click="revealNewCards">
          {{ unseenNewCards.length }} 条新反馈，点击查看
        </button>
        <WallEmptyState v-if="wallStore.cards.length === 0" />
        <div
          v-for="guide in organizeGuides"
          :key="guide.key"
          class="organize-guide"
          :class="guideToneClass(guide.tone)"
          :style="{ left: `${guide.x}px`, top: `${guide.y}px` }"
        >
          <b>{{ guide.label }}</b>
          <span>{{ guideCountText(guide.count) }}</span>
          <small>{{ guide.detail }}</small>
        </div>
        <div
          v-if="placementPreview.visible"
          class="placement-preview"
          :class="{ crowded: placementPreview.reason === 'crowded', edge: placementPreview.reason === 'edge' }"
          :style="{ left: `${placementPreview.x}px`, top: `${placementPreview.y}px` }"
        >
          <div class="tape"></div>
          <span v-if="placementPreview.reason" class="placement-preview-label">
            {{ placementPreview.reason === 'edge' ? '靠近边界' : '区域拥挤' }}
          </span>
        </div>
        <div
          v-if="snapGhost.visible"
          class="snap-ghost"
          :class="{ moving: snapGhost.moving }"
          :style="{ left: `${snapGhost.x}px`, top: `${snapGhost.y}px` }"
        >
          <div class="tape"></div>
        </div>
        <StickyCard
          v-for="item in cardsForRender"
          :key="item.card.id"
          :card="item.card"
          :is-anonymous="wallStore.wall?.is_anonymous || false"
          :organized="isOrganized"
          :highlighted="highlightedCardId === item.card.id"
          :spotlighted="wallStore.spotlightCardId === item.card.id"
          :locally-raised="locallyRaisedCardId === item.card.id"
          :breathing="canBreatheCards && highlightedCardId !== item.card.id && locallyRaisedCardId !== item.card.id"
          :can-spotlight="auth.user?.is_admin || false"
          v-bind="positionFor(item.card, item.x, item.y)"
          @pointerdown="startDrag(item.card, $event)"
          @raise="raiseCard(item.card.id)"
          @wheel="cycleLocalStack(item.card, $event)"
          @react="react(item.card, $event)"
          @spotlight="setSpotlight(item.card.id)"
          @detail="openCardDetail(item.card)"
        />
        <div
          v-for="placeholder in wallStore.placeholders"
          :key="placeholder.id"
          class="placeholder-card"
          :class="{ own: isOwnPlaceholder(placeholder.user_id) }"
          :style="{ left: `${placeholder.x}px`, top: `${placeholder.y}px` }"
        >
          <div class="tape"></div>
          <span>{{ isOwnPlaceholder(placeholder.user_id) ? '你正在输入...' : `${placeholder.user_name} 正在输入...` }}</span>
        </div>
      </section>

      <WallToolDock v-model="tool" :paused="dockPaused" :disabled-tools="disabledDockTools" />
    </section>

    <WallCreateModal v-if="showEditor" @close="closeEditor" @submit="submitCard" />

    <WallAnalysisDrawer
      v-if="showAnalysisDrawer"
      :open="showAnalysisDrawer"
      :cards="wallStore.cards"
      :summary="summary"
      :history="summaryHistory"
      :loading="summaryLoading"
      :history-loading="summaryHistoryLoading"
      :error="summaryError"
      :initial-tab="analysisTab"
      :size="analysisDrawerSize"
      @close="showAnalysisDrawer = false"
      @refresh-summary="refreshAnalysisSummary(true)"
      @export-report="exportAnalysisReport"
      @focus-cards="focusAnalysisCards"
      @tab-change="analysisTab = $event"
      @toggle-size="toggleAnalysisDrawerSize"
    />

    <WallKeywordDrawer
      v-if="showKeywordDrawer"
      :open="showKeywordDrawer"
      :cards="wallStore.cards"
      :size="keywordDrawerSize"
      @close="showKeywordDrawer = false"
      @toggle-size="toggleKeywordDrawerSize"
    />

    <WallAccessModal
      v-if="wallStore.requiresPassword"
      v-model:password="wallPassword"
      :title="wallStore.wall?.title"
      :error="wallPasswordError"
      :loading="wallPasswordLoading"
      @submit="submitWallPassword"
    />

    <CardDetailModal
      v-if="selectedCard"
      :card="selectedCard"
      :is-anonymous="wallStore.wall?.is_anonymous || false"
      :can-edit="canEditSelected"
      :is-admin="auth.user?.is_admin || false"
      :editing="editingSelected"
      :saving="detailSaving"
      :error="detailError"
      @close="closeDetail"
      @spotlight="setSpotlight"
      @delete="deleteSelectedCard"
      @submit-edit="submitSelectedEdit"
      @update:editing="editingSelected = $event"
    />

    <WallSummaryModal
      v-if="showSummary"
      :summary="summary"
      :history="summaryHistory"
      :diff="summaryDiff"
      :loading="summaryLoading"
      :history-loading="summaryHistoryLoading"
      :diff-loading="summaryDiffLoading"
      :diff-error="summaryDiffError"
      :error="summaryError"
      @close="showSummary = false"
      @refresh="openSummary(true)"
      @open-history="openHistoricalSummary"
      @compare="loadSummaryDiff"
    />

    <PresentationOverlay
      v-if="showPresentation && currentPresentationCard"
      :card="currentPresentationCard"
      :cards="presentationCards"
      :wall-title="wallStore.wall?.title"
      :is-anonymous="wallStore.wall?.is_anonymous || false"
      :active-index="presentationIndex"
      @close="stopPresentation"
      @select="presentationIndex = $event"
    />

    <LoginModal v-if="showLogin" @close="showLogin = false; load()" />
  </main>
</template>
