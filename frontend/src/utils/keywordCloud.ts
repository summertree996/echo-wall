import stopwordsZh from 'stopwords-zh'
import type { Card, Sentiment } from '../types'
import { totalReactions } from './wallAnalysis'

export type KeywordFilter = 'all' | Sentiment

export interface KeywordComment {
  id: string
  text: string
  authorName: string
  sentiment: Sentiment | null
  reactionCount: number
}

export interface KeywordCloudItem {
  text: string
  count: number
  cardCount: number
  weight: number
  sentiment: Sentiment | 'mixed'
  sentimentCounts: Record<Sentiment, number>
  reactionCount: number
  comments: KeywordComment[]
}

export interface KeywordCloudModel {
  totalCards: number
  totalTerms: number
  items: KeywordCloudItem[]
}

const MAX_COMMENTS_PER_TERM = 8
const DEFAULT_LIMIT = 80
const stopwordSet = new Set(stopwordsZh)

export function buildKeywordCloud(cards: Card[], filter: KeywordFilter = 'all', limit = DEFAULT_LIMIT): KeywordCloudModel {
  const visibleCards = cards.filter((card) => !card.is_deleted && (filter === 'all' || card.sentiment === filter))
  const buckets = new Map<string, {
    count: number
    cardIds: Set<string>
    sentimentCounts: Record<Sentiment, number>
    reactionCount: number
    comments: KeywordComment[]
  }>()

  visibleCards.forEach((card) => {
    const cardTerms = termsForCard(card)
    const reactionCount = totalReactions(card)
    cardTerms.forEach(({ text, score }) => {
      const bucket = buckets.get(text) || {
        count: 0,
        cardIds: new Set<string>(),
        sentimentCounts: { positive: 0, neutral: 0, negative: 0 },
        reactionCount: 0,
        comments: [],
      }
      bucket.count += score
      bucket.cardIds.add(card.id)
      bucket.sentimentCounts[card.sentiment || 'neutral'] += 1
      bucket.reactionCount += reactionCount
      if (!bucket.comments.some((comment) => comment.id === card.id)) {
        bucket.comments.push({
          id: card.id,
          text: card.plain_text,
          authorName: card.author_name,
          sentiment: card.sentiment,
          reactionCount,
        })
      }
      buckets.set(text, bucket)
    })
  })

  const items = [...buckets.entries()]
    .map(([text, bucket]) => {
      const cardCount = bucket.cardIds.size
      const reactionBoost = Math.log(bucket.reactionCount + 1) * 0.35
      const weight = bucket.count + cardCount * 0.75 + reactionBoost
      const comments = bucket.comments
        .sort((a, b) => b.reactionCount - a.reactionCount || a.text.localeCompare(b.text, 'zh-Hans-CN'))
        .slice(0, MAX_COMMENTS_PER_TERM)
      return {
        text,
        count: Math.round(bucket.count),
        cardCount,
        weight,
        sentiment: dominantSentiment(bucket.sentimentCounts),
        sentimentCounts: bucket.sentimentCounts,
        reactionCount: bucket.reactionCount,
        comments,
      }
    })
    .filter((item) => item.cardCount > 0 && item.weight > 0)
    .sort((a, b) => b.weight - a.weight || b.cardCount - a.cardCount || a.text.localeCompare(b.text, 'zh-Hans-CN'))
    .slice(0, limit)

  return {
    totalCards: visibleCards.length,
    totalTerms: items.length,
    items,
  }
}

function termsForCard(card: Card): Array<{ text: string; score: number }> {
  const scored = new Map<string, number>()
  extractChineseTerms(card.plain_text).forEach((term) => bump(scored, term, 1))
  card.topic_labels.forEach((label) => {
    extractChineseTerms(label).forEach((term) => bump(scored, term, 1.8))
  })
  return [...scored.entries()].map(([text, score]) => ({ text, score }))
}

function bump(map: Map<string, number>, term: string, score: number) {
  const normalized = normalizeTerm(term)
  if (!isUsefulTerm(normalized)) return
  map.set(normalized, Math.max(map.get(normalized) || 0, score))
}

function extractChineseTerms(value: string): string[] {
  const segmenter = getSegmenter()
  if (segmenter) {
    return [...segmenter.segment(value)]
      .filter((part) => part.isWordLike)
      .map((part) => part.segment)
      .flatMap(splitTerm)
  }
  return fallbackTerms(value)
}

function splitTerm(value: string): string[] {
  const normalized = normalizeTerm(value)
  if (!normalized) return []
  if (isUsefulTerm(normalized)) return [normalized]
  return fallbackTerms(normalized)
}

function fallbackTerms(value: string): string[] {
  return value.match(/[\u3400-\u9fff][\u3400-\u9fffA-Za-z0-9]{1,9}/g) || []
}

function normalizeTerm(value: string): string {
  return value
    .trim()
    .replace(/^[#＃、，。！？；："'“”‘’（）()【】\[\]{}<>《》]+|[#＃、，。！？；："'“”‘’（）()【】\[\]{}<>《》]+$/g, '')
}

function isUsefulTerm(value: string): boolean {
  if (value.length < 2 || value.length > 12) return false
  if (!/[\u3400-\u9fff]/.test(value)) return false
  if (/^\d+$/.test(value)) return false
  return !stopwordSet.has(value)
}

function dominantSentiment(counts: Record<Sentiment, number>): Sentiment | 'mixed' {
  const sorted = (Object.entries(counts) as Array<[Sentiment, number]>).sort((a, b) => b[1] - a[1])
  if (!sorted[0] || sorted[0][1] === 0) return 'mixed'
  if (sorted[1] && sorted[1][1] > 0 && sorted[0][1] === sorted[1][1]) return 'mixed'
  return sorted[0][0]
}

function getSegmenter(): Intl.Segmenter | null {
  if (typeof Intl === 'undefined' || !('Segmenter' in Intl)) return null
  return new Intl.Segmenter('zh', { granularity: 'word' })
}
