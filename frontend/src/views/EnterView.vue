<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Eye, EyeOff, LogIn, UserPlus } from '@lucide/vue'
import { useAuthStore } from '../stores/auth'
import { normalizeNextPath, resolveAfterLogin } from '../utils/entryResolver'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const nickname = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const error = ref('')

const nextPath = computed(() => normalizeNextPath(route.query.next))
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const formTitle = computed(() => (mode.value === 'login' ? '欢迎回来' : '创建账号'))

const formCopy = computed(() => {
  if (mode.value === 'register') return '留下名字，开始参与。'
  if (nextPath.value?.startsWith('/admin')) return '进入你的主持空间。'
  return '继续表达，也继续听见彼此。'
})

function switchMode(nextMode: 'login' | 'register') {
  mode.value = nextMode
  error.value = ''
  if (nextMode === 'login') {
    confirmPassword.value = ''
  }
}

async function goAfterLogin() {
  if (!auth.user) return
  await router.replace(resolveAfterLogin(auth.user, route.query.next))
}

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
    await goAfterLogin()
  } catch (err) {
    error.value = err instanceof Error ? err.message : mode.value === 'register' ? '注册失败' : '登录失败'
  }
}

onMounted(async () => {
  const user = await auth.refreshSession()
  if (user) await router.replace(resolveAfterLogin(user, route.query.next))
})
</script>

<template>
  <main class="enter-page">
    <div class="enter-dot-grid" aria-hidden="true"></div>
    <div class="enter-notes" aria-hidden="true">
      <article class="enter-note note-one">
        <p>让每一个声音，被听见。</p>
        <span>♡ 24</span>
      </article>
      <article class="enter-note note-two">
        <p>把现场的声音收在一起。</p>
        <span>？ 12</span>
      </article>
    </div>

    <form class="enter-card" @submit.prevent="submit">
      <span class="enter-brand">ECHO</span>
      <div class="enter-card-head">
        <h2>{{ formTitle }}</h2>
        <p>{{ formCopy }}</p>
      </div>

      <div class="enter-tabs">
        <button type="button" :class="{ active: mode === 'login' }" @click="switchMode('login')">
          <LogIn :size="17" />
          登录
        </button>
        <button type="button" :class="{ active: mode === 'register' }" @click="switchMode('register')">
          <UserPlus :size="17" />
          注册
        </button>
      </div>

      <label>
        邮箱
        <input v-model="email" autocomplete="email" placeholder="name@example.com" />
      </label>

      <label v-if="mode === 'register'">
        昵称
        <input v-model="nickname" autocomplete="nickname" placeholder="你的名字" />
      </label>

      <label>
        密码
        <span class="enter-password">
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
          <button type="button" @click="showPassword = !showPassword">
            <EyeOff v-if="showPassword" :size="18" />
            <Eye v-else :size="18" />
          </button>
        </span>
      </label>

      <label v-if="mode === 'register'">
        确认密码
        <input v-model="confirmPassword" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" />
      </label>

      <p v-if="error" class="enter-error">{{ error }}</p>

      <button class="enter-submit" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '请稍候' : mode === 'login' ? '继续进入' : '创建并进入' }}
        <ArrowRight :size="17" />
      </button>
    </form>
  </main>
</template>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700;800&family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap");

.enter-page {
  --enter-bg: #f4f2ef;
  --enter-bg-cool: #eef1f6;
  --enter-text-primary: #23262e;
  --enter-text-secondary: #545b68;
  --enter-text-tertiary: #8b909c;
  --enter-brand: #14161c;
  --enter-shadow: 0 1px 2px rgba(28, 30, 45, 0.08), 0 18px 42px rgba(28, 30, 45, 0.12);

  position: relative;
  isolation: isolate;
  min-height: 100vh;
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 28px;
  overflow: hidden;
  background: linear-gradient(160deg, var(--enter-bg) 0%, #fafaf8 46%, var(--enter-bg-cool) 100%);
  color: var(--enter-text-primary);
  font-family: "Noto Sans SC", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.enter-dot-grid {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: radial-gradient(circle, rgba(90, 96, 120, 0.26) 0.8px, transparent 0.8px);
  background-size: 26px 26px;
  opacity: 0.14;
  pointer-events: none;
}

.enter-notes {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.62;
  filter: blur(1px);
}

.enter-note {
  position: absolute;
  width: 228px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 16px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.54);
  box-shadow: var(--enter-shadow);
  color: #2c3038;
}

.enter-note::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(155deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0) 46%);
  pointer-events: none;
}

.enter-note p,
.enter-note span {
  position: relative;
  z-index: 1;
}

.enter-note p {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.7;
}

.enter-note span {
  color: var(--enter-text-secondary);
  font-family: "Inter", sans-serif;
  font-size: 12px;
  font-weight: 600;
}

.note-one {
  top: 13%;
  right: 13%;
  background: linear-gradient(160deg, rgba(254, 240, 244, 0.72), rgba(251, 221, 230, 0.66));
  transform: rotate(-1.2deg);
}

.note-two {
  bottom: 11%;
  left: 12%;
  background: linear-gradient(160deg, rgba(236, 244, 254, 0.72), rgba(216, 233, 252, 0.64));
  opacity: 0.62;
  transform: rotate(1.4deg) scale(0.92);
}

.enter-brand {
  justify-self: center;
  color: var(--enter-text-tertiary);
  font-family: "Inter", sans-serif;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
  line-height: 1.4;
}

.enter-card {
  position: relative;
  z-index: 1;
  width: min(430px, calc(100vw - 36px));
  display: grid;
  gap: 15px;
  border: 1px solid rgba(255, 255, 255, 0.74);
  border-radius: 24px;
  padding: 30px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 16px 44px rgba(28, 30, 45, 0.13);
  backdrop-filter: blur(18px);
}

.enter-card-head {
  display: grid;
  gap: 8px;
  margin-bottom: 2px;
  text-align: center;
}

.enter-card-head h2 {
  margin: 0;
  color: var(--enter-text-primary);
  font-size: 24px;
  line-height: 1.25;
  letter-spacing: 0;
}

.enter-card-head p {
  margin: 0;
  color: var(--enter-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}

.enter-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  border-radius: 999px;
  padding: 4px;
  background: rgba(238, 240, 245, 0.92);
}

.enter-tabs button,
.enter-password button {
  border: none;
  background: transparent;
  color: var(--ink-2);
}

.enter-tabs button {
  min-height: 40px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 700;
}

.enter-tabs button.active {
  background: #fff;
  color: var(--enter-text-primary);
  box-shadow: 0 6px 18px rgba(28, 30, 45, 0.08);
}

.enter-tabs button:focus-visible,
.enter-password button:focus-visible,
.enter-submit:focus-visible {
  outline: 3px solid rgba(91, 91, 240, 0.22);
  outline-offset: 3px;
}

.enter-card label {
  display: grid;
  gap: 8px;
  color: var(--enter-text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.enter-card input {
  width: 100%;
  height: 46px;
  border: 1px solid rgba(224, 228, 236, 0.96);
  border-radius: 12px;
  padding: 0 14px;
  outline: none;
  background: #fff;
  color: var(--enter-text-primary);
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.enter-card input:focus {
  border-color: rgba(91, 91, 240, 0.55);
  box-shadow: 0 0 0 4px rgba(91, 91, 240, 0.1);
}

.enter-password {
  position: relative;
  display: block;
}

.enter-password input {
  padding-right: 48px;
}

.enter-password button {
  position: absolute;
  right: 8px;
  top: 7px;
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 999px;
}

.enter-error {
  margin: 0;
  border-radius: 13px;
  padding: 10px 12px;
  background: rgba(239, 95, 87, 0.1);
  color: #c84339;
  font-size: 13px;
}

.enter-submit {
  min-height: 48px;
  border: none;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--enter-brand);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 10px 28px rgba(20, 22, 28, 0.16);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
}

.enter-submit:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.08);
  box-shadow: 0 14px 34px rgba(20, 22, 28, 0.2);
}

.enter-submit:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

@media (max-width: 860px) {
  .enter-page {
    padding: 22px;
  }

  .enter-notes {
    opacity: 0.28;
  }

  .note-one {
    top: 9%;
    right: 18%;
  }

  .note-two {
    display: none;
  }

  .enter-card {
    width: 100%;
    padding: 22px;
  }
}
</style>
