<script setup lang="ts">
import { MonitorPlay, X } from '@lucide/vue'
import type { Card } from '../types'

defineProps<{
  card: Card
  cards: Card[]
  wallTitle?: string | null
  isAnonymous: boolean
  activeIndex: number
}>()

const emit = defineEmits<{
  close: []
  select: [index: number]
}>()

function totalReactions(card: Card) {
  return Object.values(card.reaction_counts).reduce((sum, value) => sum + value, 0)
}
</script>

<template>
  <div class="presentation-overlay">
    <div class="presentation-actions">
      <button class="presentation-return" type="button" @click="emit('close')">回到画布</button>
      <button class="icon ghost presentation-close" type="button" aria-label="回到画布" @click="emit('close')">
        <X :size="22" />
      </button>
    </div>
    <section class="presentation-panel">
      <div class="presentation-kicker">
        <MonitorPlay :size="18" />
        <span>投屏模式 · {{ wallTitle }}</span>
      </div>
      <h2>{{ card.plain_text }}</h2>
      <div class="presentation-tags">
        <span v-if="card.sentiment">{{ card.sentiment }}</span>
        <span v-for="topic in card.topic_labels" :key="topic">#{{ topic }}</span>
      </div>
      <footer>
        <span>{{ isAnonymous ? '匿名成员' : card.author_name }}</span>
        <b>{{ totalReactions(card) }} 个反应</b>
      </footer>
      <div class="presentation-dots">
        <button
          v-for="(_card, idx) in cards"
          :key="idx"
          :class="{ active: idx === activeIndex % cards.length }"
          @click="emit('select', idx)"
        ></button>
      </div>
    </section>
  </div>
</template>
