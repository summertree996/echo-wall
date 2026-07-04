<script setup lang="ts">
import { X } from '@lucide/vue'
import RichTextEditor from './RichTextEditor.vue'

defineEmits<{
  close: []
  submit: [payload: { json: Record<string, unknown>; text: string }]
}>()
</script>

<template>
  <div class="overlay" @mousedown.self="$emit('close')">
    <section class="modal editor-modal">
      <button class="icon ghost close" type="button" @click="$emit('close')"><X :size="18" /></button>
      <h2>发表新想法</h2>
      <RichTextEditor @submit="$emit('submit', $event)" />
    </section>
  </div>
</template>
