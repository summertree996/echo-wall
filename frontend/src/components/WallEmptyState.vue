<script setup lang="ts">
import { StickyNote } from '@lucide/vue'
</script>

<template>
  <div class="empty-state">
    <StickyNote :size="42" />
    <h2>这面墙还很安静</h2>
    <p>点击画布任意位置，贴上第一张便签。</p>
  </div>
</template>
