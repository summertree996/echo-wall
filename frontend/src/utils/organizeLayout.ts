import type { Card } from '../types'

export type ViewMode = 'free' | 'sentiment' | 'topic'
export type OrganizeGuideTone = 'positive' | 'neutral' | 'negative' | 'topic'
export type TopicBucket = { key: string; label: string; count: number; order: number }
export type PositionedCard = { card: Card; x: number; y: number }
export type OrganizeGuide = {
  key: string
  label: string
  detail: string
  tone: OrganizeGuideTone
  count: number
  x: number
  y: number
}

const TOPIC_FAMILIES = [
  { key: 'ai-review', label: 'AI 整理与复盘', keywords: ['AI', '智能', '摘要', '主题', '证据', '复盘', '整理', '语境'] },
  { key: 'canvas-attention', label: '画布与注意力', keywords: ['画布', '放置', '预览', '坐标', '位置', '拖动', '注意力', '公平', '自由墙'] },
  { key: 'realtime-tech', label: '实时协作与技术', keywords: ['实时', '同步', 'WebSocket', '部署', '多墙', '持久化', '性能', '协作'] },
  { key: 'trust-anonymous', label: '匿名与信任', keywords: ['匿名', '信任', '身份', '表达'] },
  { key: 'facilitation-output', label: '主持与输出', keywords: ['Spotlight', '主持', '导出', '富文本', '可读性', '反馈', '参与感'] },
]
const CARD_CENTER_OFFSET_X = 125
const CARD_CENTER_OFFSET_Y = 86
const ORGANIZED_CARD_TOP = 320

export function totalReactions(card: Card) {
  return Object.values(card.reaction_counts).reduce((sum, value) => sum + value, 0)
}

export function buildTopicBuckets(cards: Card[]): TopicBucket[] {
  const buckets = new Map<string, TopicBucket>()
  cards.forEach((card) => {
    const bucket = topicBucketMetaFor(card)
    const existing = buckets.get(bucket.key)
    buckets.set(bucket.key, { ...bucket, count: (existing?.count || 0) + 1 })
  })
  const sorted = [...buckets.values()].sort((a, b) => a.order - b.order || b.count - a.count || a.label.localeCompare(b.label, 'zh-Hans-CN'))
  const selected = sorted.length > 6 ? sorted.slice(0, 5) : sorted
  const selectedKeys = new Set(selected.map((bucket) => bucket.key))
  let otherCount = 0
  cards.forEach((card) => {
    const key = topicBucketMetaFor(card).key
    if (!selectedKeys.has(key)) otherCount += 1
  })
  if (sorted.length > 6) {
    return [...selected, { key: '其他', label: '其他主题', count: otherCount, order: 999 }]
  }
  return selected
}

export function buildOrganizeGuides(mode: ViewMode, cards: Card[], topicBuckets: TopicBucket[]): OrganizeGuide[] {
  if (mode === 'sentiment') {
    const groups = [
      { key: 'positive', label: '正面反馈', detail: '支持、认可和可放大的声音', tone: 'positive' as OrganizeGuideTone },
      { key: 'neutral', label: '中性反馈', detail: '事实描述、建议和待确认问题', tone: 'neutral' as OrganizeGuideTone },
      { key: 'negative', label: '负面反馈', detail: '阻力、风险和需要优先处理的信号', tone: 'negative' as OrganizeGuideTone },
    ]
    return groups.map((group, index) => ({
      ...group,
      count: cards.filter((card) => (card.sentiment || 'neutral') === group.key).length,
      x: 112 + index * 360,
      y: 104,
    }))
  }
  if (mode === 'topic') {
    return topicBuckets.map((bucket, index) => ({
      key: bucket.key,
      label: bucket.label,
      detail: '按主题聚合，保留原卡片颜色',
      tone: 'topic',
      count: bucket.count,
      x: 104 + (index % 3) * 380,
      y: 104 + Math.floor(index / 3) * 520,
    }))
  }
  return []
}

export function layoutSentiment(cards: Card[]): PositionedCard[] {
  const order = ['positive', 'neutral', 'negative']
  const groups = new Map(order.map((key) => [key, [] as Card[]]))
  cards.forEach((card) => groups.get(card.sentiment || 'neutral')?.push(card))
  const startX = 112
  const colW = 360
  return order.flatMap((sentiment, col) => {
    return (groups.get(sentiment) || [])
      .sort((a, b) => totalReactions(b) - totalReactions(a))
      .map((card, idx) => ({ card, x: startX + col * colW + CARD_CENTER_OFFSET_X, y: ORGANIZED_CARD_TOP + idx * 220 + CARD_CENTER_OFFSET_Y }))
  })
}

export function layoutTopic(cards: Card[], topicBuckets: TopicBucket[]): PositionedCard[] {
  const bucketIndex = new Map(topicBuckets.map((bucket, index) => [bucket.key, index]))
  const localIndex = new Map<string, number>()
  return [...cards]
    .sort((a, b) => totalReactions(b) - totalReactions(a) || new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .map((card) => {
      const key = topicBucketKeyFor(card, topicBuckets)
      const bucket = bucketIndex.get(key) || 0
      const idx = localIndex.get(key) || 0
      localIndex.set(key, idx + 1)
      return {
        card,
        x: 104 + (bucket % 3) * 380 + (idx % 2) * 30 + CARD_CENTER_OFFSET_X,
        y: ORGANIZED_CARD_TOP + Math.floor(bucket / 3) * 520 + Math.floor(idx / 2) * 218 + CARD_CENTER_OFFSET_Y,
      }
    })
}

export function guideCountText(count: number) {
  return `${count} 张`
}

export function guideToneClass(tone: OrganizeGuideTone) {
  return `guide-${tone}`
}

function normalizedTopicLabels(card: Card) {
  return [...new Set(card.topic_labels.map((label) => label.trim()).filter(Boolean))]
}

function topicBucketMetaFor(card: Card): TopicBucket {
  const labels = normalizedTopicLabels(card)
  const haystack = labels.join(' ').toLowerCase()
  const familyIndex = TOPIC_FAMILIES.findIndex((family) => family.keywords.some((keyword) => haystack.includes(keyword.toLowerCase())))
  if (familyIndex >= 0) {
    const family = TOPIC_FAMILIES[familyIndex]
    return { key: family.key, label: family.label, count: 0, order: familyIndex }
  }
  const label = labels[0] || '未归类'
  return { key: `raw:${label}`, label, count: 0, order: 100 }
}

function topicBucketKeyFor(card: Card, topicBuckets: TopicBucket[]) {
  const selectedKeys = new Set(topicBuckets.map((bucket) => bucket.key))
  const key = topicBucketMetaFor(card).key
  return selectedKeys.has(key) ? key : '其他'
}
