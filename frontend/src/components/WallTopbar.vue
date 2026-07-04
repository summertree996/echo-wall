<script setup lang="ts">
import { computed } from 'vue'
import { Bot, Cloud, Lock, LogIn, MonitorPlay, Sparkles, Unlock } from '@lucide/vue'

type ViewMode = 'free' | 'sentiment' | 'topic'

const props = defineProps<{
  title?: string | null
  description?: string | null
  connected: boolean
  connectionLabel: string
  viewMode: ViewMode
  isAdmin: boolean
  loggedIn: boolean
  summaryLoading: boolean
  cardCount: number
  isLocked: boolean
}>()

const emit = defineEmits<{
  organize: []
  keywords: []
  presentation: []
  summary: []
  toggleLock: []
  login: []
}>()

const organizeLabel = computed(() => {
  if (props.viewMode === 'free') return '智能整理'
  if (props.viewMode === 'topic') return '主题聚类'
  return '情绪分列'
})
</script>

<template>
  <header class="wall-topbar">
    <div>
      <div class="wall-title-row">
        <h1>{{ title || '反馈墙' }}</h1>
        <span>{{ cardCount }} 张反馈</span>
      </div>
      <p v-if="description">{{ description }}</p>
    </div>
    <div class="topbar-actions">
      <span class="save-state" :class="{ on: connected }">{{ connectionLabel }}</span>
      <button v-if="isAdmin" class="secondary" @click="emit('organize')">
        <Sparkles :size="17" />{{ organizeLabel }}
      </button>
      <button v-if="isAdmin" class="secondary" @click="emit('keywords')">
        <Cloud :size="17" />关键词云
      </button>
      <button v-if="isAdmin" class="secondary" :class="{ active: isLocked }" @click="emit('toggleLock')">
        <Unlock v-if="isLocked" :size="17" />
        <Lock v-else :size="17" />
        {{ isLocked ? '继续收集' : '暂停收集' }}
      </button>
      <button v-if="isAdmin" class="secondary" title="本机投屏展示，不影响其他参与者" @click="emit('presentation')">
        <MonitorPlay :size="17" />投屏模式
      </button>
      <button v-if="isAdmin" class="secondary" :disabled="summaryLoading" @click="emit('summary')">
        <Bot :size="17" />{{ summaryLoading ? '生成中' : 'AI 摘要' }}
      </button>
      <button v-if="!loggedIn" class="primary" @click="emit('login')">
        <LogIn :size="17" />登录参与
      </button>
    </div>
  </header>
</template>
