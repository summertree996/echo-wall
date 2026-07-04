<script setup lang="ts">
import { Edit3, Sparkles, Trash2, X } from '@lucide/vue'
import RichTextEditor from './RichTextEditor.vue'
import type { Card } from '../types'

defineProps<{
  card: Card
  isAnonymous: boolean
  canEdit: boolean
  isAdmin: boolean
  editing: boolean
  saving: boolean
  error: string
}>()

const emit = defineEmits<{
  close: []
  spotlight: [cardId: string]
  delete: []
  submitEdit: [payload: { json: Record<string, unknown>; text: string }]
  'update:editing': [value: boolean]
}>()
</script>

<template>
  <div class="overlay" @mousedown.self="emit('close')">
    <section class="modal detail-modal">
      <button class="icon ghost close" type="button" @click="emit('close')"><X :size="18" /></button>
      <header class="detail-head">
        <div>
          <h2>{{ isAnonymous ? '匿名成员' : card.author_name }}</h2>
          <p>{{ new Date(card.created_at).toLocaleString() }}</p>
        </div>
        <div v-if="canEdit" class="detail-actions">
          <button v-if="isAdmin" class="secondary" :disabled="saving" @click="emit('spotlight', card.id)">
            <Sparkles :size="15" />主持聚焦
          </button>
          <button class="secondary" :disabled="saving" @click="emit('update:editing', !editing)">
            <Edit3 :size="15" />{{ editing ? '取消编辑' : '编辑' }}
          </button>
          <button class="secondary danger-action" :disabled="saving" @click="emit('delete')">
            <Trash2 :size="15" />删除
          </button>
        </div>
      </header>
      <div v-if="error" class="form-error">{{ error }}</div>
      <RichTextEditor
        v-if="editing"
        :key="card.id"
        :initial="card.content_json"
        submit-label="保存修改"
        @submit="emit('submitEdit', $event)"
      />
      <template v-else>
        <p>{{ card.plain_text }}</p>
        <div class="chips"><span v-for="topic in card.topic_labels" :key="topic">#{{ topic }}</span></div>
      </template>
    </section>
  </div>
</template>
