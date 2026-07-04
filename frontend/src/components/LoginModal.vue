<script setup lang="ts">
import { ref } from 'vue'
import { Eye, EyeOff, X } from '@lucide/vue'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()
const mode = ref<'login' | 'register'>('login')
const email = ref('demo@talon.wall')
const password = ref('demo123')
const nickname = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const error = ref('')

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

async function submit() {
  error.value = ''
  const normalizedEmail = email.value.trim()
  if (!EMAIL_PATTERN.test(normalizedEmail)) {
    error.value = '邮箱格式不正确'
    return
  }
  try {
    if (mode.value === 'register') {
      if (!nickname.value.trim()) {
        error.value = '请输入昵称'
        return
      }
      if (password.value.length < 6) {
        error.value = '密码至少 6 位'
        return
      }
      if (password.value !== confirmPassword.value) {
        error.value = '两次密码不一致'
        return
      }
      await auth.register(normalizedEmail, password.value, nickname.value.trim())
    } else {
      await auth.login(normalizedEmail, password.value)
    }
    emit('close')
  } catch (err) {
    error.value = err instanceof Error ? err.message : mode.value === 'register' ? '注册失败' : '登录失败'
  }
}

function switchMode(nextMode: 'login' | 'register') {
  mode.value = nextMode
  error.value = ''
  if (nextMode === 'register') {
    if (email.value === 'demo@talon.wall') email.value = ''
    if (password.value === 'demo123') password.value = ''
  } else {
    confirmPassword.value = ''
  }
}

function fillDemo() {
  mode.value = 'login'
  email.value = 'demo@talon.wall'
  password.value = 'demo123'
  confirmPassword.value = ''
  error.value = ''
}
</script>

<template>
  <div class="overlay" @mousedown.self="emit('close')">
    <form class="modal auth-modal" @submit.prevent="submit">
      <button class="icon ghost close" type="button" @click="emit('close')"><X :size="18" /></button>
      <div class="auth-tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button type="button" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
      </div>
      <h2>{{ mode === 'login' ? '账号登录' : '创建账号' }}</h2>
      <p>{{ mode === 'login' ? '使用演示账号可以直接进入管理台和反馈墙。' : '注册后可以在收到的墙链接里发布、反应和移动自己的卡片。' }}</p>
      <label>
        邮箱
        <input v-model="email" autocomplete="email" />
      </label>
      <label v-if="mode === 'register'">
        昵称
        <input v-model="nickname" autocomplete="nickname" placeholder="展示在卡片上的名字" />
      </label>
      <label>
        密码
        <span class="password-row">
          <input v-model="password" :type="showPassword ? 'text' : 'password'" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" />
          <button class="icon ghost" type="button" @click="showPassword = !showPassword">
            <EyeOff v-if="showPassword" :size="18" />
            <Eye v-else :size="18" />
          </button>
        </span>
      </label>
      <label v-if="mode === 'register'">
        确认密码
        <input v-model="confirmPassword" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" />
      </label>
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="primary" type="submit" :disabled="auth.loading">{{ auth.loading ? '处理中' : mode === 'login' ? '登录' : '注册并进入' }}</button>
      <button class="demo-fill" type="button" @click="fillDemo">
        演示账号 demo@talon.wall / demo123
      </button>
    </form>
  </div>
</template>
