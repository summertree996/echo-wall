<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Activity, Database, Download, LogOut, MessageCircle, Plus, RefreshCw, Shield, Users } from '@lucide/vue'
import AdminWallCard from '../components/AdminWallCard.vue'
import LoginModal from '../components/LoginModal.vue'
import { api } from '../services/api'
import { useAuthStore } from '../stores/auth'
import type { AccessMode, AuthEvent, IntegrationStatus, ResearchSummary, ResearchUserSummary, SystemStatus, Wall } from '../types'

type AiModel = Wall['ai_model']
type AiReasoningEffort = Wall['ai_reasoning_effort']

const auth = useAuthStore()
const router = useRouter()
const walls = ref<Wall[]>([])
const authEvents = ref<AuthEvent[]>([])
const systemStatus = ref<SystemStatus | null>(null)
const systemStatusLoading = ref(false)
const systemStatusError = ref('')
const wechatStatus = ref<IntegrationStatus | null>(null)
const wechatStatusError = ref('')
const researchSummary = ref<ResearchSummary | null>(null)
const researchWall = ref<Wall | null>(null)
const researchLoading = ref(false)
const researchError = ref('')
const authEventType = ref('')
const authEventEmail = ref('')
const showLogin = ref(!auth.user)
const title = ref('')
const description = ref('')
const accessMode = ref<AccessMode>('login_required')
const wallPassword = ref('')
const createError = ref('')
const aiEnabled = ref(true)
const aiModel = ref<AiModel>('deepseek-v4-flash')
const aiThinkingEnabled = ref(false)
const aiReasoningEffort = ref<AiReasoningEffort>('high')
const savingWall = reactive<Record<string, boolean>>({})
const wallPasswords = reactive<Record<string, string>>({})
const aiTestLoading = reactive<Record<string, boolean>>({})
const aiTestResults = reactive<Record<string, { status: 'ok' | 'error'; text: string }>>({})
const copiedWallId = ref<string | null>(null)
let copyFeedbackTimer: number | undefined

const activeWalls = computed(() => walls.value.filter((wall) => !wall.is_archived))
const archivedWalls = computed(() => walls.value.length - activeWalls.value.length)
const totalCards = computed(() => walls.value.reduce((sum, wall) => sum + wall.card_count, 0))

async function load() {
  const user = await auth.refreshSession()
  if (!user) {
    showLogin.value = true
    return
  }
  if (!user.is_admin) {
    router.push('/')
    return
  }
  const [wallRows] = await Promise.all([api.adminWalls(), loadAuthEvents(), loadSystemStatus(), loadWechatStatus()])
  walls.value = wallRows
}

async function loadSystemStatus() {
  systemStatusLoading.value = true
  systemStatusError.value = ''
  try {
    systemStatus.value = await api.systemStatus()
  } catch (err) {
    systemStatusError.value = err instanceof Error ? err.message : '系统自检读取失败'
  } finally {
    systemStatusLoading.value = false
  }
}

async function loadAuthEvents() {
  authEvents.value = await api.authEvents({
    event_type: authEventType.value || undefined,
    email: authEventEmail.value.trim() || undefined,
  }).catch(() => [] as AuthEvent[])
}

async function loadWechatStatus() {
  wechatStatusError.value = ''
  try {
    wechatStatus.value = await api.wechatIntegrationStatus()
  } catch (err) {
    wechatStatusError.value = err instanceof Error ? err.message : '微信集成状态读取失败'
  }
}

async function logout() {
  await auth.logout()
  router.push('/')
}

function closeLogin() {
  showLogin.value = false
  if (!auth.user) return
  if (!auth.user.is_admin) {
    router.push('/')
    return
  }
  load()
}

async function createWall() {
  if (!title.value.trim()) return
  createError.value = ''
  if (accessMode.value === 'password_required' && !wallPassword.value.trim()) {
    createError.value = '口令访问需要设置访问口令'
    return
  }
  const wall = await api.createWall({
    title: title.value.trim(),
    description: description.value.trim(),
    access_mode: accessMode.value,
    password: accessMode.value === 'password_required' ? wallPassword.value.trim() : undefined,
    ai_enabled: aiEnabled.value,
    ai_model: aiModel.value,
    ai_thinking_enabled: aiThinkingEnabled.value,
    ai_reasoning_effort: aiReasoningEffort.value,
  })
  walls.value.unshift(wall)
  title.value = ''
  description.value = ''
  accessMode.value = 'login_required'
  wallPassword.value = ''
  router.push(`/wall/${wall.id}`)
}

async function saveWallSettings(wall: Wall) {
  const password = wallPasswords[wall.id]?.trim()
  if (wall.access_mode === 'password_required' && !wall.has_password && !password) {
    window.alert('口令访问需要设置访问口令')
    return
  }
  savingWall[wall.id] = true
  try {
    const updated = await api.updateWall(wall.id, {
      access_mode: wall.access_mode,
      password: password || undefined,
      is_anonymous: wall.is_anonymous,
      is_archived: wall.is_archived,
      ai_enabled: wall.ai_enabled,
      ai_model: wall.ai_model,
      ai_thinking_enabled: wall.ai_thinking_enabled,
      ai_reasoning_effort: wall.ai_reasoning_effort,
    })
    const idx = walls.value.findIndex((item) => item.id === wall.id)
    if (idx >= 0) walls.value[idx] = updated
    wallPasswords[wall.id] = ''
  } finally {
    savingWall[wall.id] = false
  }
}

async function testWallAi(wall: Wall) {
  aiTestLoading[wall.id] = true
  aiTestResults[wall.id] = { status: 'ok', text: '正在测试当前 AI 配置...' }
  try {
    const result = await api.testWallAi(wall.id, {
      ai_model: wall.ai_model,
      ai_thinking_enabled: wall.ai_thinking_enabled,
      ai_reasoning_effort: wall.ai_reasoning_effort,
    })
    aiTestResults[wall.id] = {
      status: result.status === 'ok' ? 'ok' : 'error',
      text: `${result.message} · ${result.model} · ${result.thinking_enabled ? 'Thinking' : 'Non-thinking'} · ${result.latency_ms}ms`,
    }
  } catch (err) {
    aiTestResults[wall.id] = {
      status: 'error',
      text: err instanceof Error ? err.message : 'DeepSeek 连接测试失败',
    }
  } finally {
    aiTestLoading[wall.id] = false
  }
}

function authEventLabel(type: string) {
  if (type === 'auth:login') return '登录'
  if (type === 'auth:logout') return '登出'
  if (type === 'auth:register') return '注册'
  if (type === 'auth:login_failed') return '失败登录'
  if (type === 'auth:register_conflict') return '重复注册'
  return type
}

function statusLabel(status: SystemStatus['status']) {
  if (status === 'error') return '异常'
  if (status === 'warning') return '需注意'
  return '正常'
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function fallbackCopy(text: string) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}

async function copyLink(wall: Wall) {
  const url = `${location.origin}/wall/${wall.id}`
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(url)
    else fallbackCopy(url)
    copiedWallId.value = wall.id
    if (copyFeedbackTimer) window.clearTimeout(copyFeedbackTimer)
    copyFeedbackTimer = window.setTimeout(() => {
      copiedWallId.value = null
    }, 1800)
  } catch {
    window.prompt('复制墙链接', url)
  }
}

async function exportWall(wall: Wall) {
  const data = await api.exportWall(wall.id)
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${wall.id}-export.json`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function exportWallCsv(wall: Wall) {
  const blob = await api.exportWallCsv(wall.id)
  downloadBlob(blob, `${wall.id}-cards.csv`)
}

async function exportWallActionsCsv(wall: Wall) {
  const blob = await api.exportWallActionsCsv(wall.id)
  downloadBlob(blob, `${wall.id}-actions.csv`)
}

async function exportResearchCsv(wall: Wall) {
  const blob = await api.exportResearchCsv(wall.id)
  downloadBlob(blob, `${wall.id}-research-timeline.csv`)
}

async function openResearchSummary(wall: Wall) {
  researchWall.value = wall
  researchLoading.value = true
  researchError.value = ''
  try {
    researchSummary.value = await api.researchSummary(wall.id)
  } catch (err) {
    researchError.value = err instanceof Error ? err.message : '科研摘要读取失败'
  } finally {
    researchLoading.value = false
  }
}

async function exportResearchUserCsv(user: ResearchUserSummary) {
  if (!researchWall.value || !user.user_id) return
  const blob = await api.exportResearchUserCsv(researchWall.value.id, user.user_id)
  downloadBlob(blob, `${researchWall.value.id}-${user.user_id}-research.csv`)
}

function formatResearchSpan(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${(seconds / 3600).toFixed(1)} 小时`
}

function topResearchEvents(user: ResearchUserSummary) {
  return Object.entries(user.event_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([type, count]) => `${type} ${count}`)
    .join(' · ')
}

onMounted(load)
onUnmounted(() => {
  if (copyFeedbackTimer) window.clearTimeout(copyFeedbackTimer)
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-head">
      <div>
        <span class="eyebrow"><Shield :size="14" />管理员</span>
        <h1>主持人工作台</h1>
        <p>管理反馈墙、分享入口和现场复盘资料。</p>
      </div>
      <div class="admin-actions">
        <button class="secondary" @click="router.push('/')">返回入口</button>
        <button class="secondary" @click="logout"><LogOut :size="16" />退出</button>
      </div>
    </header>

    <div class="admin-workspace">
      <section class="admin-main">
        <section class="create-strip">
          <div class="create-copy">
            <span><Plus :size="16" />新建反馈墙</span>
            <p>创建后直接进入墙面，复制链接给参与者。</p>
          </div>
          <div class="create-fields">
            <input v-model="title" placeholder="墙标题，例如：课堂反馈 · 第 4 周" />
            <input v-model="description" placeholder="一句话说明用途" />
            <select v-model="accessMode">
              <option value="link_only">链接可浏览</option>
              <option value="login_required">登录参与</option>
              <option value="password_required">口令访问</option>
            </select>
            <input
              v-if="accessMode === 'password_required'"
              v-model="wallPassword"
              class="access-password"
              type="password"
              placeholder="访问口令"
            />
            <select v-model="aiModel">
              <option value="deepseek-v4-flash">V4 Flash</option>
              <option value="deepseek-v4-pro">V4 Pro</option>
            </select>
            <label class="inline-check"><input v-model="aiEnabled" type="checkbox" />AI 分析</label>
            <label class="inline-check"><input v-model="aiThinkingEnabled" type="checkbox" />Thinking</label>
            <select v-model="aiReasoningEffort" :disabled="!aiThinkingEnabled">
              <option value="high">High</option>
              <option value="max">Max</option>
            </select>
            <button class="primary" @click="createWall"><Plus :size="18" />创建并进入</button>
          </div>
          <div v-if="createError" class="form-error create-error">{{ createError }}</div>
        </section>

        <section class="wall-section">
          <div class="wall-section-head">
            <div>
              <h2>我的反馈墙</h2>
              <p>{{ activeWalls.length }} 面进行中，{{ totalCards }} 条反馈</p>
            </div>
            <span v-if="archivedWalls">{{ archivedWalls }} 面已归档</span>
          </div>
          <div class="wall-grid">
            <AdminWallCard
              v-for="wall in walls"
              :key="wall.id"
              :wall="wall"
              :password="wallPasswords[wall.id] || ''"
              :saving="Boolean(savingWall[wall.id])"
              :ai-test-loading="Boolean(aiTestLoading[wall.id])"
              :ai-test-result="aiTestResults[wall.id]"
              :copied="copiedWallId === wall.id"
              @open="router.push(`/wall/${$event.id}`)"
              @open-research="router.push(`/admin/walls/${$event.id}/research`)"
              @save="saveWallSettings"
              @test-ai="testWallAi"
              @export-json="exportWall"
              @export-csv="exportWallCsv"
              @export-actions-csv="exportWallActionsCsv"
              @export-research-csv="exportResearchCsv"
              @research-summary="openResearchSummary"
              @copy="copyLink"
              @update:password="wallPasswords[wall.id] = $event"
            />
          </div>
        </section>
      </section>

      <aside class="admin-aside">
        <section class="admin-aside-panel system-strip">
          <header>
            <span class="eyebrow"><Activity :size="14" />系统自检</span>
            <div class="system-status-head">
              <b :class="systemStatus?.status || 'warning'">{{ systemStatus ? statusLabel(systemStatus.status) : '未读取' }}</b>
              <button class="secondary" type="button" :disabled="systemStatusLoading" @click="loadSystemStatus">
                <RefreshCw :size="15" />{{ systemStatusLoading ? '检查中' : '刷新' }}
              </button>
            </div>
          </header>
          <p v-if="systemStatusError" class="form-error">{{ systemStatusError }}</p>
          <div v-for="check in systemStatus?.checks || []" :key="check.key" class="system-check" :class="check.status">
            <b>{{ check.label }}</b>
            <span>{{ statusLabel(check.status) }}</span>
            <small>{{ check.detail }}</small>
          </div>
        </section>

        <section class="admin-aside-panel research-strip">
          <header>
            <span class="eyebrow"><Database :size="14" />科研数据</span>
            <button
              v-if="researchWall"
              class="secondary"
              type="button"
              :disabled="researchLoading"
              @click="exportResearchCsv(researchWall)"
            >
              <Download :size="15" />全量 CSV
            </button>
          </header>
          <template v-if="researchSummary">
            <div class="research-headline">
              <b>{{ researchSummary.wall_title }}</b>
              <span>{{ researchSummary.user_count }} 个用户 · {{ researchSummary.event_count }} 条研究事件</span>
            </div>
            <div v-for="user in researchSummary.users" :key="user.actor_id" class="research-user-row">
              <div>
                <b><Users :size="14" />{{ user.user_name }}</b>
                <small>{{ user.email || user.client_session_ids[0] || '访客会话' }}</small>
              </div>
              <span>{{ user.event_count }} 条 · {{ formatResearchSpan(user.active_span_seconds) }}</span>
              <small>{{ topResearchEvents(user) || '暂无事件分布' }}</small>
              <button class="secondary" type="button" :disabled="!user.user_id" @click="exportResearchUserCsv(user)">
                <Download :size="14" />导出用户
              </button>
            </div>
          </template>
          <p v-else-if="researchLoading" class="auth-empty">正在读取用户研究摘要</p>
          <p v-else-if="researchError" class="form-error">{{ researchError }}</p>
          <p v-else class="auth-empty">在反馈墙卡片里点击用户研究摘要查看。</p>
        </section>

        <details class="admin-aside-panel integration-strip">
          <summary>
            <span class="eyebrow"><MessageCircle :size="14" />扩展入口</span>
            <b>{{ wechatStatus?.label || '微信机器人' }}</b>
          </summary>
          <p v-if="wechatStatusError" class="form-error">{{ wechatStatusError }}</p>
          <template v-else>
            <p>{{ wechatStatus?.message || '正在读取扩展状态...' }}</p>
            <div v-if="wechatStatus" class="integration-meta">
              <span>{{ wechatStatus.enabled ? '已启用' : '未启用' }}</span>
            </div>
            <button class="secondary" type="button" @click="router.push('/admin/wechat-assistant')">
              <MessageCircle :size="15" />打开微信助手
            </button>
            <div class="integration-requirements">
              <article v-for="item in wechatStatus?.requirements || []" :key="item.title">
                <b>{{ item.title }}</b>
                <small>{{ item.detail }}</small>
              </article>
            </div>
          </template>
        </details>

        <details class="admin-aside-panel auth-audit-strip">
          <summary>
            <b>最近认证事件</b>
            <span>{{ authEvents.length }} 条</span>
          </summary>
          <div class="auth-audit-filters">
            <select v-model="authEventType" @change="loadAuthEvents">
              <option value="">全部类型</option>
              <option value="auth:login">登录</option>
              <option value="auth:logout">登出</option>
              <option value="auth:login_failed">失败登录</option>
              <option value="auth:register">注册</option>
              <option value="auth:register_conflict">重复注册</option>
            </select>
            <input v-model="authEventEmail" placeholder="邮箱筛选" @keyup.enter="loadAuthEvents" />
            <button class="secondary" type="button" @click="loadAuthEvents">筛选</button>
          </div>
          <div v-for="event in authEvents" :key="event.id" class="auth-event-row">
            <span>{{ authEventLabel(event.event_type) }}</span>
            <b>{{ event.email }}</b>
            <small>{{ new Date(event.created_at).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</small>
          </div>
          <p v-if="!authEvents.length" class="auth-empty">暂无匹配的认证事件</p>
        </details>
      </aside>
    </div>

    <LoginModal v-if="showLogin" @close="closeLogin" />
  </main>
</template>
