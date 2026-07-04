<script setup lang="ts">
type ViewMode = 'free' | 'sentiment' | 'topic'

defineProps<{
  viewMode: ViewMode
  organizedPendingCount: number
  spotlightText?: string
  canCancelSpotlight: boolean
}>()

defineEmits<{
  exitOrganize: []
  clearSpotlight: []
}>()
</script>

<template>
  <div v-if="viewMode !== 'free'" class="organize-banner">
    <b>{{ viewMode === 'topic' ? '主题岛屿' : '情绪分列' }}</b>
    <span>当前只调整查看方式，内容保持原样。</span>
    <span v-if="organizedPendingCount" class="organize-pending">
      {{ organizedPendingCount }} 条新反馈在自由墙中等待查看
    </span>
    <button v-if="organizedPendingCount" class="ghost-button" @click="$emit('exitOrganize')">返回自由墙</button>
  </div>
  <div v-if="spotlightText" class="spotlight-banner">
    <b>Spotlight</b>
    <span>{{ spotlightText }}</span>
    <button v-if="canCancelSpotlight" class="ghost-button" @click="$emit('clearSpotlight')">取消聚焦</button>
  </div>
</template>
