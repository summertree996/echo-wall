import type { Card, ReactionType, Sentiment, SummaryPoint, WallSummary } from '../types'

export type AnalysisTab = 'overview' | 'sentiment' | 'topic' | 'summary'
export type AnalysisGroupType = 'sentiment' | 'topic'
export type AnalysisTone = Sentiment | 'neutral' | 'topic'

export interface AnalysisComment {
  id: string
  text: string
  authorName: string
  sentiment: Sentiment | null
  reactionCount: number
  reactionCounts: Record<ReactionType, number> | null
  topicLabels: string[]
  createdAt: string
}

export interface SentimentAnalysisGroup {
  key: Sentiment
  label: string
  compactLabel: string
  tone: Sentiment
  count: number
  percent: number
  keywords: string[]
  comments: AnalysisComment[]
  allComments: AnalysisComment[]
  hiddenCount: number
}

export interface TopicAnalysisGroup {
  key: string
  label: string
  tone: AnalysisTone
  count: number
  percent: number
  heat: number
  keywords: string[]
  summary: string
  comments: AnalysisComment[]
  allComments: AnalysisComment[]
  hiddenCount: number
}

export interface OverviewIssue {
  key: string
  title: string
  body: string
  tone: AnalysisTone
  count: number
  heat: number
  comments: AnalysisComment[]
  allComments: AnalysisComment[]
  hiddenCount: number
}

export interface WallAnalysisModel {
  cardCount: number
  reactionCount: number
  headline: string
  subline: string
  sentimentGroups: SentimentAnalysisGroup[]
  topicGroups: TopicAnalysisGroup[]
  overviewIssues: OverviewIssue[]
  prompts: string[]
}

const REPRESENTATIVE_LIMIT = 3

const SENTIMENT_META: Record<Sentiment, { label: string; compactLabel: string }> = {
  positive: { label: '正向亮点', compactLabel: '正向' },
  neutral: { label: '中性观察', compactLabel: '中性' },
  negative: { label: '负向反馈', compactLabel: '负向' },
}

const TOPIC_FAMILIES = [
  { key: 'ai-review', label: 'AI 整理与复盘', keywords: ['AI', '智能', '摘要', '主题', '证据', '复盘', '整理', '语境'] },
  { key: 'canvas-attention', label: '画布与注意力', keywords: ['画布', '放置', '预览', '坐标', '位置', '拖动', '注意力', '公平', '自由墙'] },
  { key: 'realtime-tech', label: '实时协作与技术', keywords: ['实时', '同步', 'WebSocket', '部署', '多墙', '持久化', '性能', '协作'] },
  { key: 'trust-anonymous', label: '匿名与信任', keywords: ['匿名', '信任', '身份', '表达'] },
  { key: 'facilitation-output', label: '主持与输出', keywords: ['Spotlight', '主持', '导出', '富文本', '可读性', '反馈', '参与感'] },
]

export function buildWallAnalysis(cards: Card[], summary: WallSummary | null): WallAnalysisModel {
  const visibleCards = cards.filter((card) => !card.is_deleted)
  const cardCount = visibleCards.length
  const reactionCount = visibleCards.reduce((sum, card) => sum + totalReactions(card), 0)
  const sentimentGroups = buildSentimentGroups(visibleCards)
  const topicGroups = buildTopicGroups(visibleCards)
  const overviewIssues = buildOverviewIssues(summary, topicGroups, visibleCards)
  const leadingSentiment = [...sentimentGroups].sort((a, b) => b.count - a.count)[0]
  const leadingTopic = topicGroups[0]
  const headline = summary?.overview || fallbackHeadline(leadingSentiment, leadingTopic, cardCount)
  const subline = buildSubline(cardCount, topicGroups.length, leadingSentiment)

  return {
    cardCount,
    reactionCount,
    headline,
    subline,
    sentimentGroups,
    topicGroups,
    overviewIssues,
    prompts: buildPrompts(summary, sentimentGroups, topicGroups),
  }
}

export function totalReactions(card: Card): number {
  return Object.values(card.reaction_counts).reduce((sum, value) => sum + value, 0)
}

export function commentFromCard(card: Card): AnalysisComment {
  return {
    id: card.id,
    text: card.plain_text,
    authorName: card.author_name,
    sentiment: card.sentiment,
    reactionCount: totalReactions(card),
    reactionCounts: card.reaction_counts,
    topicLabels: card.topic_labels,
    createdAt: card.created_at,
  }
}

export function sentimentText(sentiment: Sentiment | null): string {
  if (!sentiment) return '未标注'
  return SENTIMENT_META[sentiment].compactLabel
}

function buildSentimentGroups(cards: Card[]): SentimentAnalysisGroup[] {
  const total = cards.length || 1
  return (['positive', 'neutral', 'negative'] as Sentiment[]).map((key) => {
    const groupCards = cards
      .filter((card) => (card.sentiment || 'neutral') === key)
      .sort(compareCards)
    const allComments = groupCards.map(commentFromCard)
    const comments = allComments.slice(0, REPRESENTATIVE_LIMIT)
    return {
      key,
      label: SENTIMENT_META[key].label,
      compactLabel: SENTIMENT_META[key].compactLabel,
      tone: key,
      count: groupCards.length,
      percent: Math.round((groupCards.length / total) * 100),
      keywords: topKeywords(groupCards),
      comments,
      allComments,
      hiddenCount: Math.max(0, allComments.length - comments.length),
    }
  })
}

function buildTopicGroups(cards: Card[]): TopicAnalysisGroup[] {
  const bucketCards = new Map<string, { key: string; label: string; order: number; cards: Card[] }>()
  cards.forEach((card) => {
    const meta = topicMetaFor(card)
    const existing = bucketCards.get(meta.key)
    if (existing) existing.cards.push(card)
    else bucketCards.set(meta.key, { ...meta, cards: [card] })
  })

  const sorted = [...bucketCards.values()]
    .sort((a, b) => a.order - b.order || b.cards.length - a.cards.length || a.label.localeCompare(b.label, 'zh-Hans-CN'))

  const selected = sorted.length > 6 ? sorted.slice(0, 5) : sorted
  const selectedKeys = new Set(selected.map((bucket) => bucket.key))
  const otherCards = sorted
    .filter((bucket) => !selectedKeys.has(bucket.key))
    .flatMap((bucket) => bucket.cards)
  const finalBuckets = otherCards.length
    ? [...selected, { key: 'other', label: '其他主题', order: 999, cards: otherCards }]
    : selected
  const total = cards.length || 1

  return finalBuckets
    .map((bucket) => {
      const orderedCards = bucket.cards.sort(compareCards)
      const heat = orderedCards.reduce((sum, card) => sum + totalReactions(card), 0)
      const allComments = orderedCards.map(commentFromCard)
      const comments = allComments.slice(0, REPRESENTATIVE_LIMIT)
      return {
        key: bucket.key,
        label: bucket.label,
        tone: dominantSentiment(orderedCards),
        count: orderedCards.length,
        percent: Math.round((orderedCards.length / total) * 100),
        heat,
        keywords: topKeywords(orderedCards),
        summary: topicSummary(bucket.label, orderedCards),
        comments,
        allComments,
        hiddenCount: Math.max(0, allComments.length - comments.length),
      }
    })
    .sort((a, b) => b.heat - a.heat || b.count - a.count)
}

function buildOverviewIssues(summary: WallSummary | null, topicGroups: TopicAnalysisGroup[], cards: Card[]): OverviewIssue[] {
  if (summary?.key_points.length) {
    const cardsById = new Map(cards.map((card) => [card.id, card]))
    return summary.key_points.slice(0, 4).map((point, index) => overviewIssueFromSummary(point, index, cardsById))
  }
  return topicGroups.slice(0, 4).map((topic) => ({
    key: topic.key,
    title: topic.label,
    body: topic.summary,
    tone: topic.tone,
    count: topic.count,
    heat: topic.heat,
    comments: topic.comments,
    allComments: topic.allComments,
    hiddenCount: topic.hiddenCount,
  }))
}

function overviewIssueFromSummary(point: SummaryPoint, index: number, cardsById: Map<string, Card>): OverviewIssue {
  const allComments = point.evidence.map((evidence) => {
    const card = cardsById.get(evidence.id)
    if (card) return commentFromCard(card)
    return {
      id: evidence.id,
      text: evidence.text,
      authorName: '原始卡片',
      sentiment: evidence.sentiment,
      reactionCount: evidence.reaction_count,
      reactionCounts: null,
      topicLabels: [],
      createdAt: '',
    }
  })
  const comments = allComments.slice(0, REPRESENTATIVE_LIMIT)
  return {
    key: `${point.title}-${index}`,
    title: point.title,
    body: point.summary,
    tone: comments[0]?.sentiment || 'topic',
    count: allComments.length,
    heat: allComments.reduce((sum, comment) => sum + comment.reactionCount, 0),
    comments,
    allComments,
    hiddenCount: Math.max(0, allComments.length - comments.length),
  }
}

function buildPrompts(summary: WallSummary | null, sentimentGroups: SentimentAnalysisGroup[], topicGroups: TopicAnalysisGroup[]): string[] {
  if (summary?.risks.length) {
    return summary.risks.slice(0, 2).map((risk) => `回应${risk.title}`)
  }
  const concernKeywords = sentimentGroups.find((group) => group.key === 'negative')?.keywords || []
  const topTopic = topicGroups[0]?.label
  return [
    concernKeywords[0] ? `先看${concernKeywords[0]}` : '先看关注项',
    topTopic ? `追问${topTopic}` : '追问高互动卡片',
  ]
}

function fallbackHeadline(leadingSentiment: SentimentAnalysisGroup | undefined, leadingTopic: TopicAnalysisGroup | undefined, cardCount: number): string {
  if (!cardCount) return '暂无反馈'
  const sentiment = leadingSentiment?.compactLabel || '反馈'
  const topic = leadingTopic?.label || '主要议题'
  return `${sentiment}占比最高，${topic}最集中`
}

function buildSubline(cardCount: number, topicCount: number, leadingSentiment: SentimentAnalysisGroup | undefined): string {
  if (!cardCount) return '等待新反馈'
  const sentiment = leadingSentiment ? `${leadingSentiment.compactLabel} ${leadingSentiment.percent}%` : '情绪待判断'
  return `${cardCount} 条反馈 · ${topicCount} 个主题 · ${sentiment}`
}

function compareCards(a: Card, b: Card): number {
  return totalReactions(b) - totalReactions(a) || new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
}

function dominantSentiment(cards: Card[]): AnalysisTone {
  const counts = cards.reduce<Record<Sentiment, number>>((result, card) => {
    result[card.sentiment || 'neutral'] += 1
    return result
  }, { positive: 0, neutral: 0, negative: 0 })
  return (Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] as Sentiment) || 'topic'
}

function topKeywords(cards: Card[], limit = 3): string[] {
  const counts = new Map<string, number>()
  cards.forEach((card) => {
    card.topic_labels.forEach((label) => {
      const key = label.trim()
      if (key) counts.set(key, (counts.get(key) || 0) + 1)
    })
  })
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'zh-Hans-CN'))
    .slice(0, limit)
    .map(([label]) => label)
}

function topicSummary(label: string, cards: Card[]): string {
  const keywords = topKeywords(cards, 2)
  if (keywords.length) return `${label}集中在${keywords.join('、')}`
  return `${label}有持续反馈`
}

function topicMetaFor(card: Card): { key: string; label: string; order: number } {
  const labels = [...new Set(card.topic_labels.map((label) => label.trim()).filter(Boolean))]
  const haystack = labels.join(' ').toLowerCase()
  const familyIndex = TOPIC_FAMILIES.findIndex((family) => family.keywords.some((keyword) => haystack.includes(keyword.toLowerCase())))
  if (familyIndex >= 0) {
    const family = TOPIC_FAMILIES[familyIndex]
    return { key: family.key, label: family.label, order: familyIndex }
  }
  const label = labels[0] || '未归类'
  return { key: `raw:${label}`, label, order: 100 }
}
