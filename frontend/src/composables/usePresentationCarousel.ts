import { computed, ref } from 'vue'
import type { Card } from '../types'
import { totalReactions } from '../utils/organizeLayout'

export function usePresentationCarousel(cards: () => Card[], featuredCard?: () => Card | null) {
  const showPresentation = ref(false)
  const presentationIndex = ref(0)
  let presentationTimer: number | undefined

  const presentationCards = computed(() => {
    const sorted = [...cards()]
      .sort((a, b) => totalReactions(b) - totalReactions(a) || new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    const featured = featuredCard?.()
    const ordered = featured ? [featured, ...sorted.filter((card) => card.id !== featured.id)] : sorted
    return ordered.slice(0, 5)
  })

  const currentPresentationCard = computed(() => {
    if (!presentationCards.value.length) return null
    return presentationCards.value[presentationIndex.value % presentationCards.value.length]
  })

  function startPresentation() {
    if (!presentationCards.value.length) return
    showPresentation.value = true
    presentationIndex.value = 0
    if (presentationTimer) window.clearInterval(presentationTimer)
    presentationTimer = window.setInterval(() => {
      presentationIndex.value = (presentationIndex.value + 1) % presentationCards.value.length
    }, 5200)
  }

  function stopPresentation() {
    showPresentation.value = false
    if (presentationTimer) window.clearInterval(presentationTimer)
    presentationTimer = undefined
  }

  return {
    showPresentation,
    presentationCards,
    currentPresentationCard,
    presentationIndex,
    startPresentation,
    stopPresentation,
  }
}
