import { ref } from 'vue'
import { api } from '../services/api'
import type { WallSummary, WallSummaryDiff, WallSummaryHistoryItem } from '../types'

type OpenSummaryOptions = {
  visible?: boolean
}

export function useWallSummary(wallId: () => string, canUseSummary: () => boolean) {
  const showSummary = ref(false)
  const summaryLoading = ref(false)
  const summaryError = ref('')
  const summary = ref<WallSummary | null>(null)
  const summaryDiff = ref<WallSummaryDiff | null>(null)
  const summaryDiffLoading = ref(false)
  const summaryDiffError = ref('')
  const summaryHistory = ref<WallSummaryHistoryItem[]>([])
  const summaryHistoryLoading = ref(false)

  async function openSummary(refresh = false, options: OpenSummaryOptions = {}) {
    if (!canUseSummary()) return
    if (options.visible !== false) showSummary.value = true
    summaryLoading.value = true
    summaryError.value = ''
    summaryDiff.value = null
    summaryDiffError.value = ''
    const history = await loadSummaryHistory()
    if (!refresh && !summary.value && history[0]) {
      try {
        summary.value = await api.wallSummaryHistoryItem(wallId(), history[0].id)
      } catch {
        summary.value = null
      }
    }
    try {
      summary.value = await api.wallSummary(wallId(), refresh)
      await loadSummaryHistory()
    } catch (err) {
      summaryError.value = err instanceof Error ? err.message : '摘要生成失败'
    } finally {
      summaryLoading.value = false
    }
  }

  async function loadSummaryHistory(): Promise<WallSummaryHistoryItem[]> {
    if (!canUseSummary()) return []
    summaryHistoryLoading.value = true
    try {
      summaryHistory.value = await api.wallSummaryHistory(wallId())
      return summaryHistory.value
    } catch {
      summaryHistory.value = []
      return []
    } finally {
      summaryHistoryLoading.value = false
    }
  }

  async function openHistoricalSummary(item: WallSummaryHistoryItem) {
    if (!canUseSummary()) return
    summaryLoading.value = true
    summaryError.value = ''
    summaryDiff.value = null
    summaryDiffError.value = ''
    try {
      summary.value = await api.wallSummaryHistoryItem(wallId(), item.id)
    } catch (err) {
      summaryError.value = err instanceof Error ? err.message : '历史摘要读取失败'
    } finally {
      summaryLoading.value = false
    }
  }

  async function loadSummaryDiff() {
    if (!canUseSummary() || !summary.value?.summary_id) return
    summaryDiffLoading.value = true
    summaryDiffError.value = ''
    try {
      summaryDiff.value = await api.wallSummaryDiff(wallId(), summary.value.summary_id)
    } catch (err) {
      summaryDiff.value = null
      summaryDiffError.value = err instanceof Error ? err.message : '暂无上一版可对比'
    } finally {
      summaryDiffLoading.value = false
    }
  }

  return {
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
  }
}
