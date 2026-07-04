import { nextTick, reactive, ref, type ComputedRef, type Ref } from 'vue'
import type { Card, Placeholder, User } from '../types'
import { previewPlacementReason, type PlacementReason } from '../utils/placementPreview'

type Tool = 'add' | 'react' | 'drag'
type EditorPayload = { json: Record<string, unknown>; text: string }

export function useCardCreation(options: {
  tool: Ref<Tool>
  interactionPaused: ComputedRef<boolean> | Ref<boolean>
  canvasRef: Ref<HTMLElement | null>
  user: () => User | null
  requiresPassword: () => boolean
  cards: () => Card[]
  placeholders: () => Placeholder[]
  requestLogin: () => void
  createPlaceholder: (payload: { x: number; y: number; canvas_width: number; color_hint?: string }) => Promise<Placeholder | null>
  renewPlaceholder: (placeholderId: string) => Promise<Placeholder | null>
  releasePlaceholder: (placeholderId: string) => Promise<void>
  createCard: (payload: {
    content_json: Record<string, unknown>
    plain_text: string
    x: number
    y: number
    canvas_width?: number
    placeholder_id?: string
  }) => Promise<Card | null>
}) {
  const showEditor = ref(false)
  const editorPoint = reactive({ x: 260, y: 220 })
  const placementPreview = reactive({ visible: false, x: 0, y: 0, reason: '' as PlacementReason })
  const snapGhost = reactive({ visible: false, moving: false, x: 0, y: 0 })
  const placementHint = ref('')
  const highlightedCardId = ref<string | null>(null)
  const currentPlaceholderId = ref<string | null>(null)
  let renewTimer: number | undefined
  let placementHintTimer: number | undefined
  let snapGhostTimer: number | undefined
  let highlightTimer: number | undefined

  function canPreviewPlacement() {
    return options.tool.value === 'add' &&
      !options.interactionPaused.value &&
      !showEditor.value &&
      Boolean(options.user()) &&
      !options.requiresPassword()
  }

  function updatePlacementPreview(event: PointerEvent | MouseEvent) {
    if (!canPreviewPlacement() || !options.canvasRef.value) {
      placementPreview.visible = false
      return
    }
    const rect = options.canvasRef.value.getBoundingClientRect()
    placementPreview.x = Math.round(event.clientX - rect.left)
    placementPreview.y = Math.round(event.clientY - rect.top + options.canvasRef.value.scrollTop)
    placementPreview.reason = previewPlacementReason({
      x: placementPreview.x,
      y: placementPreview.y,
      canvasWidth: options.canvasRef.value.clientWidth,
      cards: options.cards(),
      placeholders: options.placeholders(),
      ignorePlaceholderId: currentPlaceholderId.value,
    })
    placementPreview.visible = placementPreview.reason !== 'edge'
  }

  function hidePlacementPreview() {
    placementPreview.visible = false
  }

  function showPlacementHint(text: string) {
    placementHint.value = text
    if (placementHintTimer) window.clearTimeout(placementHintTimer)
    placementHintTimer = window.setTimeout(() => {
      placementHint.value = ''
    }, 3200)
  }

  function wait(ms: number) {
    return new Promise((resolve) => window.setTimeout(resolve, ms))
  }

  function showSnapGhost(from: { x: number; y: number }, to: { x: number; y: number }) {
    if (snapGhostTimer) window.clearTimeout(snapGhostTimer)
    snapGhost.visible = true
    snapGhost.moving = false
    snapGhost.x = from.x
    snapGhost.y = from.y
    window.requestAnimationFrame(() => {
      snapGhost.moving = true
      snapGhost.x = to.x
      snapGhost.y = to.y
    })
    snapGhostTimer = window.setTimeout(() => {
      snapGhost.visible = false
      snapGhost.moving = false
    }, 680)
  }

  async function highlightCard(card: Card, options: { scroll?: boolean; duration?: number } = {}) {
    highlightedCardId.value = card.id
    if (highlightTimer) window.clearTimeout(highlightTimer)
    await nextTick()
    if (options.scroll !== false) {
      document.querySelector<HTMLElement>(`[data-card-id="${card.id}"]`)?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'center',
      })
    }
    highlightTimer = window.setTimeout(() => {
      highlightedCardId.value = null
    }, options.duration ?? 2400)
  }

  async function openEditor(event: MouseEvent) {
    if (options.tool.value !== 'add' || options.interactionPaused.value) return
    if (options.requiresPassword()) return
    hidePlacementPreview()
    if (!options.user()) {
      options.requestLogin()
      return
    }
    const target = event.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    editorPoint.x = Math.round(event.clientX - rect.left)
    editorPoint.y = Math.round(event.clientY - rect.top + target.scrollTop)
    const requested = { x: editorPoint.x, y: editorPoint.y }
    const placeholder = await options.createPlaceholder({
      x: editorPoint.x,
      y: editorPoint.y,
      canvas_width: target.clientWidth,
      color_hint: 'yellow',
    })
    if (placeholder) {
      currentPlaceholderId.value = placeholder.id
      editorPoint.x = placeholder.x
      editorPoint.y = placeholder.y
      const distance = Math.hypot(placeholder.x - requested.x, placeholder.y - requested.y)
      if (distance > 36) {
        showSnapGhost(requested, { x: placeholder.x, y: placeholder.y })
        showPlacementHint(distance > 160 ? '这一区域比较满，已帮你贴到附近空位。' : '已吸附到附近空位。')
        await wait(220)
      }
      startRenewLoop()
    }
    showEditor.value = true
  }

  async function submitCard(payload: EditorPayload) {
    const card = await options.createCard({
      content_json: payload.json,
      plain_text: payload.text,
      x: editorPoint.x,
      y: editorPoint.y,
      canvas_width: options.canvasRef.value?.clientWidth,
      placeholder_id: currentPlaceholderId.value || undefined,
    })
    stopRenewLoop()
    currentPlaceholderId.value = null
    showEditor.value = false
    if (card) await highlightCard(card)
  }

  function startRenewLoop() {
    stopRenewLoop()
    renewTimer = window.setInterval(() => {
      if (currentPlaceholderId.value) void options.renewPlaceholder(currentPlaceholderId.value)
    }, 18000)
  }

  function stopRenewLoop() {
    if (renewTimer) window.clearInterval(renewTimer)
    renewTimer = undefined
  }

  async function closeEditor() {
    showEditor.value = false
    stopRenewLoop()
    if (currentPlaceholderId.value) {
      const id = currentPlaceholderId.value
      currentPlaceholderId.value = null
      await options.releasePlaceholder(id)
    }
  }

  function disposeCardCreation() {
    stopRenewLoop()
    if (currentPlaceholderId.value) {
      const id = currentPlaceholderId.value
      currentPlaceholderId.value = null
      void options.releasePlaceholder(id)
    }
    if (placementHintTimer) window.clearTimeout(placementHintTimer)
    if (snapGhostTimer) window.clearTimeout(snapGhostTimer)
    if (highlightTimer) window.clearTimeout(highlightTimer)
  }

  return {
    showEditor,
    editorPoint,
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
  }
}
