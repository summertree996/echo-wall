<script setup lang="ts">
import { computed } from 'vue'
import { Expand, Heart, MessageCircleQuestion, Sparkles, ThumbsDown } from '@lucide/vue'
import type { Card, ReactionType } from '../types'

const props = defineProps<{
  card: Card
  isAnonymous: boolean
  organized?: boolean
  highlighted?: boolean
  spotlighted?: boolean
  locallyRaised?: boolean
  breathing?: boolean
  canSpotlight?: boolean
  x?: number
  y?: number
}>()
const emit = defineEmits<{
  pointerdown: [event: PointerEvent]
  react: [reaction: ReactionType]
  detail: []
  spotlight: []
  raise: []
  wheel: [event: WheelEvent]
}>()

const cardLayerZIndex = computed(() => Math.min(Math.max(props.card.z_index || 1, 1), 60))
const breathSeed = computed(() => hashText(props.card.id))
const style = computed<Record<string, string | number>>(() => ({
  left: `${props.x ?? props.card.x}px`,
  top: `${props.y ?? props.card.y}px`,
  zIndex: props.spotlighted ? 900 : props.locallyRaised ? 70 : cardLayerZIndex.value,
  transform: props.spotlighted
    ? 'translate(-50%, -50%) rotate(0deg) scale(1.28)'
    : props.organized ? 'translate(-50%, -50%) rotate(0deg)' : `translate(-50%, -50%) rotate(${props.card.rotation}deg)`,
  '--breath-delay': `${-(breathSeed.value % 6200)}ms`,
  '--breath-duration': `${6200 + (breathSeed.value % 1800)}ms`,
  '--breath-lift': `${1 + (breathSeed.value % 5) * 0.16}px`,
}))

function hashText(text: string) {
  let hash = 0
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0
  }
  return hash
}

const sentimentLabel: Record<string, string> = { positive: '亮点', neutral: '观察', negative: '关注' }
const visibleTopics = computed(() => props.card.topic_labels.slice(0, 2))
const hiddenTopicCount = computed(() => Math.max(0, props.card.topic_labels.length - visibleTopics.value.length))
const reactions: Array<{ type: ReactionType; icon: any; label: string }> = [
  { type: 'like', icon: Heart, label: '喜欢' },
  { type: 'dislike', icon: ThumbsDown, label: '不喜欢' },
  { type: 'question', icon: MessageCircleQuestion, label: '疑问' },
]
</script>

<template>
  <article
    class="sticky-card"
    :data-card-id="card.id"
    :class="[
      `note-${card.color}`,
      card.sentiment && `sent-${card.sentiment}`,
      highlighted && 'just-created',
      spotlighted && 'spotlight-card',
      locallyRaised && 'locally-raised',
      organized && 'organized-card',
      breathing && 'breathing',
    ]"
    :style="style"
    tabindex="0"
    @pointerenter="emit('raise')"
    @mouseenter="emit('raise')"
    @focusin="emit('raise')"
    @click="emit('raise')"
    @wheel.stop.prevent="emit('wheel', $event)"
    @pointerdown="emit('pointerdown', $event)"
  >
    <div class="card-top-actions">
      <button v-if="canSpotlight" class="spotlight-action" title="主持聚焦" @pointerdown.stop @click.stop="emit('spotlight')"><Sparkles :size="15" /></button>
      <button class="expand" title="查看详情" @pointerdown.stop @click.stop="emit('detail')"><Expand :size="15" /></button>
    </div>
    <div class="tape"></div>
    <p class="note-text">{{ card.plain_text }}</p>
    <div class="chips">
      <span v-if="card.sentiment" class="mood">{{ sentimentLabel[card.sentiment] }}</span>
      <span v-for="topic in visibleTopics" :key="topic">#{{ topic }}</span>
      <span v-if="hiddenTopicCount">+{{ hiddenTopicCount }}</span>
    </div>
    <div class="card-reactions">
      <button v-for="item in reactions" :key="item.type" :class="{ on: card.own_reactions.includes(item.type) }" :title="item.label" @pointerdown.stop @click.stop="emit('react', item.type)">
        <component :is="item.icon" :size="15" />
        <small>{{ item.label }}</small>
        <span>{{ card.reaction_counts[item.type] || '' }}</span>
      </button>
    </div>
    <footer>
      <div class="avatar">{{ (isAnonymous ? '匿' : card.author_name).slice(0, 1) }}</div>
      <div class="meta">
        <b>{{ isAnonymous ? '匿名成员' : card.author_name }}</b>
        <small>{{ new Date(card.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</small>
      </div>
    </footer>
  </article>
</template>
