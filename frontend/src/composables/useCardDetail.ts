import { computed, ref } from 'vue'
import type { Card, User } from '../types'

type CardEditPayload = { content_json: Record<string, unknown>; plain_text: string }

export function useCardDetail(
  cards: () => Card[],
  currentUser: () => User | null,
  updateCard: (cardId: string, payload: CardEditPayload) => Promise<Card | null>,
  deleteCard: (cardId: string) => Promise<void>,
) {
  const selectedCardId = ref<string | null>(null)
  const editingSelected = ref(false)
  const detailSaving = ref(false)
  const detailError = ref('')

  const selectedCard = computed(() => cards().find((card) => card.id === selectedCardId.value) || null)
  const canEditSelected = computed(() => {
    const user = currentUser()
    return Boolean(user && selectedCard.value && (selectedCard.value.author_id === user.id || user.is_admin))
  })

  function openDetail(card: Card) {
    selectedCardId.value = card.id
    editingSelected.value = false
    detailError.value = ''
  }

  function closeDetail() {
    selectedCardId.value = null
    editingSelected.value = false
    detailError.value = ''
  }

  async function submitSelectedEdit(payload: { json: Record<string, unknown>; text: string }) {
    if (!selectedCard.value) return
    detailSaving.value = true
    detailError.value = ''
    try {
      await updateCard(selectedCard.value.id, {
        content_json: payload.json,
        plain_text: payload.text,
      })
      editingSelected.value = false
    } catch (err) {
      detailError.value = err instanceof Error ? err.message : '保存失败'
    } finally {
      detailSaving.value = false
    }
  }

  async function deleteSelectedCard() {
    if (!selectedCard.value) return
    const ok = window.confirm('确认删除这张卡片？')
    if (!ok) return
    detailSaving.value = true
    detailError.value = ''
    try {
      await deleteCard(selectedCard.value.id)
      closeDetail()
    } catch (err) {
      detailError.value = err instanceof Error ? err.message : '删除失败'
    } finally {
      detailSaving.value = false
    }
  }

  return {
    selectedCard,
    canEditSelected,
    editingSelected,
    detailSaving,
    detailError,
    openDetail,
    closeDetail,
    submitSelectedEdit,
    deleteSelectedCard,
  }
}
