import { nextTick, onMounted, onUnmounted, watch, type Ref } from 'vue'
import type { ResearchEventPayload } from '../types'

interface TrackOptions {
  targetType?: string | null
  targetId?: string | null
  x?: number | null
  y?: number | null
  payload?: Record<string, unknown>
}

interface ResearchTelemetryOptions {
  wallId: () => string
  enabled: () => boolean
  stageRef: Ref<HTMLElement | null>
  canvasRef: Ref<HTMLElement | null>
  viewMode: () => string
  tool: () => string
  cardCount: () => number
  send: (events: ResearchEventPayload[]) => Promise<void>
}

const SESSION_KEY = 'talon_research_session_id'
const MAX_QUEUE_SIZE = 240
const FLUSH_INTERVAL_MS = 4500
const MOUSE_SAMPLE_MS = 900
const SCROLL_SAMPLE_MS = 1400

function createId(prefix: string) {
  if (crypto?.randomUUID) return `${prefix}_${crypto.randomUUID().replaceAll('-', '').slice(0, 18)}`
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

function researchSessionId() {
  try {
    const existing = localStorage.getItem(SESSION_KEY)
    if (existing) return existing
    const next = createId('rs')
    localStorage.setItem(SESSION_KEY, next)
    return next
  } catch {
    return createId('rs')
  }
}

export function useResearchTelemetry(options: ResearchTelemetryOptions) {
  const sessionId = researchSessionId()
  let eventIndex = 0
  let flushTimer: number | undefined
  let lastMouseSampleAt = 0
  let lastScrollSampleAt = 0
  let observer: IntersectionObserver | null = null
  const visibleCards = new Set<string>()
  const queue: ResearchEventPayload[] = []

  function canvasPoint(event: MouseEvent | PointerEvent) {
    const canvas = options.canvasRef.value
    if (!canvas) return { x: null, y: null }
    const rect = canvas.getBoundingClientRect()
    return {
      x: Math.round(event.clientX - rect.left),
      y: Math.round(event.clientY - rect.top),
    }
  }

  function commonPayload(extra: Record<string, unknown> = {}) {
    return {
      path: location.pathname,
      view_mode: options.viewMode(),
      tool: options.tool(),
      card_count: options.cardCount(),
      ...extra,
    }
  }

  async function flush() {
    if (!queue.length) return
    const events = queue.splice(0, queue.length)
    try {
      await options.send(events)
    } catch {
      queue.unshift(...events.slice(-MAX_QUEUE_SIZE))
      if (queue.length > MAX_QUEUE_SIZE) queue.splice(0, queue.length - MAX_QUEUE_SIZE)
    }
  }

  function track(eventType: string, trackOptions: TrackOptions = {}) {
    if (!options.enabled()) return
    const canvas = options.canvasRef.value
    const event: ResearchEventPayload = {
      client_session_id: sessionId,
      client_event_id: `${sessionId}:${eventIndex++}`,
      event_type: eventType,
      target_type: trackOptions.targetType || null,
      target_id: trackOptions.targetId || null,
      x: trackOptions.x ?? null,
      y: trackOptions.y ?? null,
      viewport_width: window.innerWidth,
      viewport_height: window.innerHeight,
      canvas_width: canvas?.offsetWidth || null,
      canvas_height: canvas?.offsetHeight || null,
      payload: commonPayload(trackOptions.payload || {}),
      client_ts: new Date().toISOString(),
    }
    queue.push(event)
    if (queue.length >= 28) void flush()
    if (queue.length > MAX_QUEUE_SIZE) queue.splice(0, queue.length - MAX_QUEUE_SIZE)
  }

  function handleMouseMove(event: MouseEvent) {
    const now = Date.now()
    if (now - lastMouseSampleAt < MOUSE_SAMPLE_MS) return
    lastMouseSampleAt = now
    const point = canvasPoint(event)
    track('pointer:sample', { targetType: 'canvas', ...point })
  }

  function handleScroll() {
    const now = Date.now()
    if (now - lastScrollSampleAt < SCROLL_SAMPLE_MS) return
    lastScrollSampleAt = now
    const stage = options.stageRef.value
    track('stage:scroll', {
      targetType: 'wall',
      payload: {
        scroll_top: stage?.scrollTop || 0,
        scroll_left: stage?.scrollLeft || 0,
      },
    })
  }

  function handleClick(event: MouseEvent) {
    if (!(event.target instanceof Element)) return
    const cardElement = event.target.closest('[data-card-id]') as HTMLElement | null
    const point = canvasPoint(event)
    track('ui:click', {
      targetType: cardElement ? 'card' : 'canvas',
      targetId: cardElement?.dataset.cardId || null,
      ...point,
    })
  }

  function bindDom() {
    options.canvasRef.value?.addEventListener('mousemove', handleMouseMove, { passive: true })
    options.canvasRef.value?.addEventListener('click', handleClick, { capture: true })
    options.stageRef.value?.addEventListener('scroll', handleScroll, { passive: true })
  }

  function unbindDom() {
    options.canvasRef.value?.removeEventListener('mousemove', handleMouseMove)
    options.canvasRef.value?.removeEventListener('click', handleClick, { capture: true } as EventListenerOptions)
    options.stageRef.value?.removeEventListener('scroll', handleScroll)
  }

  function refreshCardObserver() {
    observer?.disconnect()
    visibleCards.clear()
    const canvas = options.canvasRef.value
    if (!canvas || !options.enabled()) return
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const element = entry.target as HTMLElement
          const cardId = element.dataset.cardId
          if (!cardId || !entry.isIntersecting || visibleCards.has(cardId)) continue
          visibleCards.add(cardId)
          const rect = element.getBoundingClientRect()
          track('card:visible', {
            targetType: 'card',
            targetId: cardId,
            payload: {
              ratio: Number(entry.intersectionRatio.toFixed(3)),
              top: Math.round(rect.top),
              left: Math.round(rect.left),
            },
          })
        }
      },
      { root: options.stageRef.value, threshold: 0.5 },
    )
    canvas.querySelectorAll<HTMLElement>('[data-card-id]').forEach((item) => observer?.observe(item))
  }

  function start() {
    bindDom()
    flushTimer = window.setInterval(() => void flush(), FLUSH_INTERVAL_MS)
    track('session:start', {
      targetType: 'wall',
      payload: {
        user_agent: navigator.userAgent,
        language: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      },
    })
    void nextTick(refreshCardObserver)
  }

  function stop() {
    unbindDom()
    observer?.disconnect()
    observer = null
    if (flushTimer) window.clearInterval(flushTimer)
    flushTimer = undefined
    void flush()
  }

  onMounted(() => {
    if (options.enabled()) start()
  })

  watch(() => options.enabled(), async (enabled) => {
    stop()
    if (enabled) {
      await nextTick()
      start()
    }
  })

  watch(() => options.cardCount(), async () => {
    await nextTick()
    refreshCardObserver()
  })

  onUnmounted(stop)

  return {
    track,
    flush,
  }
}
