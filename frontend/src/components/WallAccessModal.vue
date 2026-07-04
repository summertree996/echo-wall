<script setup lang="ts">
import { KeyRound } from '@lucide/vue'

defineProps<{
  title?: string
  password: string
  error: string
  loading: boolean
}>()

const emit = defineEmits<{
  submit: []
  'update:password': [value: string]
}>()

function updatePassword(event: Event) {
  emit('update:password', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="overlay">
    <form class="modal access-modal" @submit.prevent="emit('submit')">
      <div class="access-icon"><KeyRound :size="24" /></div>
      <h2>输入访问口令</h2>
      <p>{{ title }} 设置了访问口令，输入后本机将记住这面墙的访问状态。</p>
      <input
        :value="password"
        type="password"
        autocomplete="current-password"
        placeholder="访问口令"
        @input="updatePassword"
      />
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="primary" type="submit" :disabled="loading || !password.trim()">
        {{ loading ? '校验中' : '进入墙面' }}
      </button>
    </form>
  </div>
</template>
