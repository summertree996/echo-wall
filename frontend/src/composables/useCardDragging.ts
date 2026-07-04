import { ref, type ComputedRef, type Ref } from 'vue'
import type { Card, User } from '../types'

type Tool = 'add' | 'react' | 'drag'
type DragPreview = { card_id: string; x: number; y: number } | null

interface DragSession {
  id: string
  sx: number
  sy: number
  ox: number
  oy: number
  x: number
  y: number
  moved: boolean
  pointerId: number
  target: HTMLElement
}

export function useCardDragging(options: {
  tool: Ref<Tool>
  interactionPaused: ComputedRef<boolean> | Ref<boolean>
  canvasRef: Ref<HTMLElement | null>
  user: () => User | null
  dragPreview: () => DragPreview
  sendTransient: (cardId: string, x: number, y: number) => void
  moveCard: (cardId: string, x: number, y: number, canvasWidth?: number) => Promise<void>
}) {
  const drag = ref<DragSession | null>(null)

  function canDrag(card: Card) {
    const user = options.user()
    if (options.interactionPaused.value || options.tool.value !== 'drag' || !user) return false
    return card.author_id === user.id || user.is_admin
  }

  function startDrag(card: Card, event: PointerEvent) {
    if (!canDrag(card)) return
    const target = event.currentTarget as HTMLElement
    target.setPointerCapture(event.pointerId)
    drag.value = {
      id: card.id,
      sx: event.clientX,
      sy: event.clientY,
      ox: card.x,
      oy: card.y,
      x: card.x,
      y: card.y,
      moved: false,
      pointerId: event.pointerId,
      target,
    }
  }

  function onPointerMove(event: PointerEvent) {
    if (!drag.value || drag.value.pointerId !== event.pointerId) return
    const dx = event.clientX - drag.value.sx
    const dy = event.clientY - drag.value.sy
    drag.value.x = Math.round(drag.value.ox + dx)
    drag.value.y = Math.round(drag.value.oy + dy)
    drag.value.moved = Math.abs(dx) + Math.abs(dy) > 4
    options.sendTransient(drag.value.id, drag.value.x, drag.value.y)
  }

  async function finishDrag(commit: boolean) {
    if (!drag.value) return
    const done = drag.value
    drag.value = null
    if (done.target.hasPointerCapture(done.pointerId)) {
      done.target.releasePointerCapture(done.pointerId)
    }
    if (commit && done.moved) {
      await options.moveCard(done.id, done.x, done.y, options.canvasRef.value?.clientWidth)
    }
  }

  async function onPointerUp(event: PointerEvent) {
    if (!drag.value || drag.value.pointerId !== event.pointerId) return
    await finishDrag(true)
  }

  async function onPointerCancel(event: PointerEvent) {
    if (!drag.value || drag.value.pointerId !== event.pointerId) return
    await finishDrag(false)
  }

  function positionFor(card: Card, proposedX: number, proposedY: number) {
    if (drag.value?.id === card.id) return { x: drag.value.x, y: drag.value.y }
    const preview = options.dragPreview()
    if (preview?.card_id === card.id) return { x: preview.x, y: preview.y }
    return { x: proposedX, y: proposedY }
  }

  return {
    drag,
    startDrag,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
    positionFor,
  }
}
