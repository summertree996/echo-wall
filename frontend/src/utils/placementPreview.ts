import type { Card, Placeholder } from '../types'

export const CARD_WIDTH = 250
export const CARD_HEIGHT = 170
export const TERRITORY_WIDTH = 258
export const TERRITORY_HEIGHT = 184

export type PlacementReason = '' | 'crowded' | 'edge'

export type PlacementRect = {
  left: number
  top: number
  right: number
  bottom: number
}

export function territoryFor(x: number, y: number): PlacementRect {
  const halfW = TERRITORY_WIDTH / 2
  const halfH = TERRITORY_HEIGHT / 2
  return { left: x - halfW, top: y - halfH, right: x + halfW, bottom: y + halfH }
}

export function overlaps(a: PlacementRect, b: PlacementRect) {
  return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
}

export function previewPlacementReason(input: {
  x: number
  y: number
  canvasWidth: number
  cards: Card[]
  placeholders: Placeholder[]
  ignorePlaceholderId?: string | null
}): PlacementReason {
  if (input.x < CARD_WIDTH / 2 || input.x > input.canvasWidth - CARD_WIDTH / 2 || input.y < CARD_HEIGHT / 2) {
    return 'edge'
  }
  const previewRect = territoryFor(input.x, input.y)
  const cardRects = input.cards.map((card) => territoryFor(card.x, card.y))
  const placeholderRects = input.placeholders
    .filter((item) => item.id !== input.ignorePlaceholderId)
    .map((item) => territoryFor(item.x, item.y))
  return [...cardRects, ...placeholderRects].some((rect) => overlaps(previewRect, rect)) ? 'crowded' : ''
}
