<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'
import { ArrowLeft, Bot, CheckCircle2, MessageCircle, QrCode, RefreshCw, Send, Settings, Shield, TestTube2 } from '@lucide/vue'
import LoginModal from '../components/LoginModal.vue'
import { api } from '../services/api'
import { useAuthStore } from '../stores/auth'
import type { Wall, WechatAssistantConnection, WechatAssistantQrcode, WechatAssistantStatus, WechatAssistantTimelineItem } from '../types'

const router = useRouter()
const auth = useAuthStore()

const status = ref<WechatAssistantStatus | null>(null)
const connections = ref<WechatAssistantConnection[]>([])
const walls = ref<Wall[]>([])
const timeline = ref<WechatAssistantTimelineItem[]>([])
const qrcode = ref<WechatAssistantQrcode | null>(null)
const qrcodeImageSrc = ref('')
const selectedConnectionId = ref('')
const selectedWallId = ref('')
const queryText = ref('帮我看看这面墙现在主要在说什么，有哪些适合现场讨论的代表评论？')
const pushText = ref('测试下推：如果你收到这条消息，说明 ECHO 微信助手发送链路正常。')
const testResult = ref('')
const pushResult = ref('')
const errorText = ref('')
const loading = ref(false)
const actionLoading = ref('')
const showLogin = ref(!auth.user)
let pollTimer: number | undefined
let monitorTimer: number | undefined
let qrRenderSeq = 0

const selectedConnection = computed(() => connections.value.find((item) => item.id === selectedConnectionId.value) || null)
const selectedWall = computed(() => walls.value.find((item) => item.id === selectedWallId.value) || null)
const providerKind = computed(() => status.value?.provider.kind || '')
const providerLabel = computed(() => {
  if (providerKind.value === 'HttpWechatAssistantProvider') return '生产 HTTP/iLink'
  if (providerKind.value === 'MockWechatAssistantProvider') return '本地测试'
  return providerKind.value || '未知'
})
const isMockProvider = computed(() => providerKind.value === 'MockWechatAssistantProvider')
const latestWechatUser = computed(() => (
  timeline.value.find((item) => item.external_user_id && !item.external_user_id.startsWith('admin-'))?.external_user_id || ''
))
const workerLabel = computed(() => {
  const worker = status.value?.worker
  if (!worker) return '监听状态未知'
  if (worker.running) return `自动监听中，每 ${worker.poll_interval_seconds} 秒`
  if (worker.enabled) return '监听已启用，后端未运行'
  return '自动监听关闭'
})
const monitorTitle = computed(() => {
  if (!selectedConnection.value) return '未选择连接'
  return `${shortId(selectedConnection.value.id)} · ${statusLabel(selectedConnection.value.status)}`
})
const monitorSubtitle = computed(() => {
  if (!selectedConnection.value) return '选择一个连接后查看对应对话'
  const account = selectedConnection.value.provider_account_id || '未绑定账号'
  const user = latestWechatUser.value ? `最近会话 ${shortId(latestWechatUser.value)}` : '等待微信侧发来消息'
  return `${account} · ${user}`
})

function shortId(value: string | null | undefined) {
  if (!value) return '未设置'
  if (value.length <= 12) return value
  return `${value.slice(0, 8)}…${value.slice(-4)}`
}

function formatTime(value: string | null | undefined) {
  if (!value) return '未完成'
  return new Date(value).toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function statusLabel(value: string) {
  if (value === 'connected') return '已连接'
  if (value === 'pending_qrcode') return '待扫码'
  if (value === 'disconnected') return '已断开'
  if (value === 'expired') return '已过期'
  if (value === 'error') return '错误'
  if (value === 'available') return '可用'
  return value
}

function directionLabel(value: string) {
  return value === 'outbound' ? '发出' : '收到'
}

function policyLabel(value: string | null) {
  if (value === 'onboarding') return '引导'
  if (value === 'thinking') return '处理中'
  if (value === 'reply') return '回复'
  if (value === 'manual_test') return '手动下推'
  if (value === 'local_test') return '本地模拟'
  return value || '消息'
}

function deliveryLabel(value: string) {
  if (value === 'sent') return '已发送'
  if (value === 'failed') return '发送失败'
  if (value === 'processed') return '已处理'
  if (value === 'received') return '已接收'
  if (value === 'pending') return '待发送'
  if (value === 'local_only') return '仅本地'
  return value
}

async function displayableQrcodeSource(value: string) {
  const seq = ++qrRenderSeq
  qrcodeImageSrc.value = ''
  const source = value.trim()
  if (!source) return ''
  if (source.startsWith('data:image/')) {
    qrcodeImageSrc.value = source
    return source
  }
  if (/^https?:\/\/.+\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(source)) {
    qrcodeImageSrc.value = source
    return source
  }
  if (/^[A-Za-z0-9+/=\s]+$/.test(source) && source.length > 200) {
    const image = `data:image/png;base64,${source.replace(/\s+/g, '')}`
    qrcodeImageSrc.value = image
    return image
  }
  try {
    const image = await QRCode.toDataURL(source, {
      width: 224,
      margin: 1,
      errorCorrectionLevel: 'M',
    })
    if (seq === qrRenderSeq) {
      qrcodeImageSrc.value = image
    }
    return image
  } catch {
    if (seq === qrRenderSeq) {
      qrcodeImageSrc.value = source
    }
    return source
  }
}

async function loadAll() {
  errorText.value = ''
  loading.value = true
  try {
    const user = await auth.refreshSession()
    if (!user) {
      showLogin.value = true
      return
    }
    if (!user.is_admin) {
      router.push('/')
      return
    }
    const [statusPayload, connectionRows, wallRows] = await Promise.all([
      api.wechatAssistantStatus(),
      api.wechatAssistantConnections(),
      api.adminWalls(),
    ])
    status.value = statusPayload
    connections.value = connectionRows
    walls.value = wallRows.filter((wall) => !wall.is_archived)
    if (!selectedConnectionId.value && connectionRows.length) {
      selectedConnectionId.value = connectionRows[0].id
    }
    const current = connectionRows.find((item) => item.id === selectedConnectionId.value) || connectionRows[0]
    if (!selectedWallId.value) {
      selectedWallId.value = current?.current_wall_id || ''
    }
    await loadTimeline()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '微信助手数据读取失败'
  } finally {
    loading.value = false
  }
}

async function refreshMonitor() {
  try {
    const [statusPayload, connectionRows, timelineRows] = await Promise.all([
      api.wechatAssistantStatus(),
      api.wechatAssistantConnections(),
      api.wechatAssistantTimeline(80, selectedConnectionId.value || undefined),
    ])
    status.value = statusPayload
    connections.value = connectionRows
    timeline.value = timelineRows
  } catch {
    // keep the current monitor snapshot
  }
}

async function requestQrcode() {
  actionLoading.value = 'qrcode'
  errorText.value = ''
  try {
    qrcode.value = await api.requestWechatAssistantQrcode()
    await displayableQrcodeSource(qrcode.value.qrcode_url)
    selectedConnectionId.value = qrcode.value.connection_id
    selectedWallId.value = ''
    await loadAll()
    startPolling()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '二维码申请失败'
  } finally {
    actionLoading.value = ''
  }
}

async function pollQrcode() {
  const id = qrcode.value?.connection_id || selectedConnectionId.value
  if (!id) return
  try {
    const row = await api.pollWechatAssistantQrcode(id)
    const idx = connections.value.findIndex((item) => item.id === row.id)
    if (idx >= 0) connections.value[idx] = row
    if (row.status === 'connected') {
      stopPolling()
      qrcode.value = null
      qrcodeImageSrc.value = ''
      await loadAll()
    }
  } catch {
    stopPolling()
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(pollQrcode, 1800)
}

function startMonitor() {
  stopMonitor()
  monitorTimer = window.setInterval(refreshMonitor, 3000)
}

function stopMonitor() {
  if (monitorTimer) window.clearInterval(monitorTimer)
  monitorTimer = undefined
}

function stopPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = undefined
}

async function mockConfirm() {
  const id = selectedConnectionId.value || qrcode.value?.connection_id
  if (!id) return
  actionLoading.value = 'mock'
  errorText.value = ''
  try {
    await api.mockConfirmWechatAssistant(id)
    qrcode.value = null
    qrcodeImageSrc.value = ''
    stopPolling()
    await loadAll()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '模拟确认失败'
  } finally {
    actionLoading.value = ''
  }
}

async function saveCurrentWall() {
  if (!selectedConnectionId.value) return
  actionLoading.value = 'wall'
  errorText.value = ''
  try {
    const updated = await api.setWechatAssistantCurrentWall(selectedConnectionId.value, selectedWallId.value || null)
    const idx = connections.value.findIndex((item) => item.id === updated.id)
    if (idx >= 0) connections.value[idx] = updated
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '默认墙保存失败'
  } finally {
    actionLoading.value = ''
  }
}

async function sendTestQuery() {
  if (!selectedConnectionId.value || !queryText.value.trim()) return
  actionLoading.value = 'query'
  errorText.value = ''
  testResult.value = ''
  try {
    const result = await api.testWechatAssistantQuery(selectedConnectionId.value, {
      text: queryText.value.trim(),
      wall_id: selectedWallId.value || undefined,
    })
    testResult.value = result.reply || '没有返回内容'
    await loadTimeline()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '测试提问失败'
  } finally {
    actionLoading.value = ''
  }
}

async function loadConversation() {
  try {
    await loadTimeline()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '聊天记录读取失败'
  }
}

async function loadTimeline() {
  timeline.value = await api.wechatAssistantTimeline(80, selectedConnectionId.value || undefined)
}

async function pollSelectedConnectionOnce() {
  if (!selectedConnectionId.value) return
  actionLoading.value = 'poll'
  errorText.value = ''
  try {
    await api.pollWechatAssistantOnce(selectedConnectionId.value)
    await refreshMonitor()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '立即拉取失败'
  } finally {
    actionLoading.value = ''
  }
}

async function sendWechatTestPush() {
  if (!selectedConnectionId.value || !pushText.value.trim()) return
  actionLoading.value = 'push'
  errorText.value = ''
  pushResult.value = ''
  try {
    const result = await api.testWechatAssistantSend(selectedConnectionId.value, {
      text: pushText.value.trim(),
    })
    pushResult.value = result.delivery_status === 'sent'
      ? `已下推到 ${shortId(result.external_user_id)}`
      : `下推失败：${result.delivery_reason || result.delivery_status}`
    await refreshMonitor()
  } catch (err) {
    errorText.value = err instanceof Error ? err.message : '测试下推失败'
  } finally {
    actionLoading.value = ''
  }
}

function closeLogin() {
  showLogin.value = false
  loadAll()
}

watch(selectedConnectionId, (connectionId) => {
  const connection = connections.value.find((item) => item.id === connectionId)
  selectedWallId.value = connection?.current_wall_id || ''
  testResult.value = ''
  pushResult.value = ''
  loadTimeline().catch(() => undefined)
})

onMounted(async () => {
  await loadAll()
  startMonitor()
})
onUnmounted(() => {
  stopPolling()
  stopMonitor()
})
</script>

<template>
  <main class="wechat-page">
    <header class="wechat-head">
      <div>
        <span class="eyebrow"><Bot :size="14" />AI 微信助手</span>
        <h1>微信侧反馈墙讨论</h1>
        <p>管理员通过私聊查询反馈墙概况、代表评论、风险点和复盘建议。</p>
      </div>
      <div class="head-actions">
        <button class="secondary" @click="router.push('/admin/walls')"><ArrowLeft :size="16" />管理台</button>
        <button class="secondary" :disabled="loading" @click="loadAll"><RefreshCw :size="16" />刷新</button>
      </div>
    </header>

    <p v-if="errorText" class="wechat-error">{{ errorText }}</p>

    <section class="status-band">
      <article>
        <span><Shield :size="16" />状态</span>
        <b>{{ status ? statusLabel(status.status) : '读取中' }}</b>
        <small>{{ status?.connected_count || 0 }} 条已连接，{{ providerLabel }}，{{ workerLabel }}</small>
      </article>
      <article>
        <span><MessageCircle :size="16" />记录</span>
        <b>{{ timeline.length }} 条</b>
        <small>最近微信对话时间线</small>
      </article>
      <article>
        <span><Settings :size="16" />默认墙</span>
        <b>{{ selectedWall?.title || '未选择' }}</b>
        <small>{{ selectedWall ? `${selectedWall.card_count} 条反馈` : '选择一面墙后可测试提问' }}</small>
      </article>
    </section>

    <div class="wechat-grid">
      <section class="panel connect-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow"><QrCode :size="14" />连接</span>
            <h2>扫码连接</h2>
          </div>
          <button class="primary" :disabled="actionLoading === 'qrcode'" @click="requestQrcode">
            <QrCode :size="17" />{{ actionLoading === 'qrcode' ? '申请中' : '新建连接' }}
          </button>
        </div>

        <div v-if="qrcode" class="qrcode-box">
          <img :src="qrcodeImageSrc || qrcode.qrcode_url" alt="微信连接二维码" />
          <div>
            <b>等待微信确认</b>
            <small>{{ qrcode.connection_id }}</small>
            <button v-if="isMockProvider" class="secondary" :disabled="actionLoading === 'mock'" @click="mockConfirm">
              <CheckCircle2 :size="16" />{{ actionLoading === 'mock' ? '确认中' : '本地模拟确认' }}
            </button>
          </div>
        </div>

        <div class="connection-list">
          <button
            v-for="connection in connections"
            :key="connection.id"
            class="connection-row"
            :class="{ active: connection.id === selectedConnectionId }"
            @click="selectedConnectionId = connection.id; selectedWallId = connection.current_wall_id || ''"
          >
            <span>{{ statusLabel(connection.status) }}</span>
            <b>{{ shortId(connection.id) }}</b>
            <small>{{ connection.provider_account_id || '未绑定账号' }}</small>
          </button>
          <p v-if="!connections.length" class="empty-copy">暂无微信连接</p>
        </div>
      </section>

      <section class="panel inbox-panel">
        <div class="panel-head monitor-head">
          <div>
            <span class="eyebrow"><MessageCircle :size="14" />记录</span>
            <h2>对话监控</h2>
            <small class="panel-subtitle">{{ monitorTitle }}，{{ monitorSubtitle }}</small>
          </div>
          <div class="panel-actions">
            <button
              class="secondary"
              :disabled="selectedConnection?.status !== 'connected' || actionLoading === 'poll'"
              @click="pollSelectedConnectionOnce"
            >
              <RefreshCw :size="16" />{{ actionLoading === 'poll' ? '拉取中' : '立即拉取' }}
            </button>
            <button class="secondary" @click="loadConversation"><RefreshCw :size="16" />刷新</button>
          </div>
        </div>
        <div class="message-list monitor-list">
          <article
            v-for="item in timeline"
            :key="item.id"
            class="message-item timeline-item"
            :class="item.direction"
          >
            <div class="message-meta">
              <span>{{ directionLabel(item.direction) }} · {{ item.direction === 'outbound' ? policyLabel(item.delivery_policy) : item.message_type }}</span>
              <small>{{ deliveryLabel(item.delivery_status) }} · {{ formatTime(item.timestamp) }}</small>
            </div>
            <p class="message-user">{{ item.text_content || '无文字内容' }}</p>
            <small>{{ shortId(item.external_user_id) }}<template v-if="item.delivery_reason"> · {{ item.delivery_reason }}</template></small>
          </article>
          <p v-if="!timeline.length" class="empty-copy">当前连接暂无聊天内容</p>
        </div>
      </section>

      <section class="panel config-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow"><Settings :size="14" />配置</span>
            <h2>默认讨论墙</h2>
          </div>
        </div>

        <label>
          <span>当前连接</span>
          <select v-model="selectedConnectionId">
            <option v-for="connection in connections" :key="connection.id" :value="connection.id">
              {{ shortId(connection.id) }} · {{ statusLabel(connection.status) }}
            </option>
          </select>
        </label>

        <label>
          <span>反馈墙</span>
          <select v-model="selectedWallId">
            <option value="">不预设</option>
            <option v-for="wall in walls" :key="wall.id" :value="wall.id">
              {{ wall.title }} · {{ wall.card_count }} 条
            </option>
          </select>
        </label>

        <button class="secondary" :disabled="!selectedConnectionId || actionLoading === 'wall'" @click="saveCurrentWall">
          <CheckCircle2 :size="16" />{{ actionLoading === 'wall' ? '保存中' : '保存默认墙' }}
        </button>

        <div class="current-detail">
          <span>连接 ID</span><b>{{ shortId(selectedConnection?.id) }}</b>
          <span>账号</span><b>{{ selectedConnection?.provider_account_id || '未设置' }}</b>
          <span>更新时间</span><b>{{ formatTime(selectedConnection?.updated_at) }}</b>
        </div>
      </section>

      <section class="panel query-panel">
        <div class="panel-head">
          <div>
            <span class="eyebrow"><TestTube2 :size="14" />测试</span>
            <h2>手动测试</h2>
          </div>
        </div>
        <div class="test-grid">
          <div class="test-block">
            <label>
              <span>下推到微信</span>
              <textarea v-model="pushText" class="compact-textarea" />
            </label>
            <button
              class="primary"
              :disabled="selectedConnection?.status !== 'connected' || !latestWechatUser || actionLoading === 'push'"
              @click="sendWechatTestPush"
            >
              <Send :size="16" />{{ actionLoading === 'push' ? '发送中' : latestWechatUser ? '测试下推' : '等待微信会话' }}
            </button>
            <small>{{ latestWechatUser ? `将发送到 ${shortId(latestWechatUser)}` : '微信侧先发一条消息后才能下推' }}</small>
            <p v-if="pushResult" class="test-result">{{ pushResult }}</p>
          </div>
          <div class="test-block">
            <label>
              <span>模拟微信提问</span>
              <textarea v-model="queryText" class="compact-textarea" />
            </label>
            <button class="secondary" :disabled="selectedConnection?.status !== 'connected' || actionLoading === 'query'" @click="sendTestQuery">
              <Send :size="16" />{{ actionLoading === 'query' ? '思考中' : selectedConnection?.status === 'connected' ? '本地模拟' : '先完成扫码' }}
            </button>
            <p v-if="testResult" class="test-result">{{ testResult }}</p>
          </div>
        </div>
      </section>
    </div>

    <LoginModal v-if="showLogin" @close="closeLogin" />
  </main>
</template>

<style scoped>
.wechat-page {
  min-height: 100vh;
  padding: 32px;
  background: #f6f3ee;
  color: #22252c;
}

.wechat-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 20px;
}

.wechat-head h1,
.panel h2 {
  margin: 0;
  letter-spacing: 0;
}

.wechat-head h1 { font-size: 30px; }
.wechat-head p { margin: 8px 0 0; color: #68707d; line-height: 1.55; }

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #5b5bf0;
  font-size: 12px;
  font-weight: 800;
}

.head-actions,
.panel-actions,
.panel-head,
.status-band,
.connection-row,
.message-meta {
  display: flex;
  align-items: center;
}

.head-actions { gap: 8px; }
.panel-actions {
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

button {
  border: 0;
  border-radius: 14px;
  min-height: 38px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-weight: 800;
}

button:disabled { opacity: 0.55; cursor: not-allowed; }
.primary { background: #5b5bf0; color: #fff; }
.secondary { background: #fff; color: #333746; border: 1px solid #e4e7ef; }

.wechat-error {
  margin: 0 0 14px;
  color: #b64034;
  font-weight: 700;
}

.status-band {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.status-band article,
.panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e8e4dc;
  box-shadow: 0 18px 44px rgba(31, 34, 41, 0.08);
}

.status-band article {
  border-radius: 18px;
  padding: 16px;
  display: grid;
  gap: 5px;
}

.status-band span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #68707d;
  font-size: 13px;
}

.status-band b { font-size: 20px; }
.status-band small,
.panel small,
.empty-copy { color: #68707d; }

.wechat-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.72fr) minmax(560px, 1.28fr);
  gap: 14px;
  align-items: start;
}

.connect-panel {
  grid-column: 1;
  grid-row: 1;
}

.config-panel {
  grid-column: 2;
  grid-row: 2;
}

.inbox-panel {
  grid-column: 2;
  grid-row: 1;
  align-self: start;
  display: flex;
  flex-direction: column;
}

.query-panel {
  grid-column: 1;
  grid-row: 2;
}

.panel {
  border-radius: 20px;
  padding: 18px;
  display: grid;
  gap: 14px;
}

.panel-head {
  justify-content: space-between;
  gap: 12px;
}

.monitor-head {
  align-items: flex-start;
}

.panel-subtitle {
  display: block;
  margin-top: 4px;
  max-width: 620px;
}

.qrcode-box {
  display: grid;
  grid-template-columns: 128px 1fr;
  gap: 14px;
  align-items: center;
  padding: 12px;
  border-radius: 16px;
  background: #f8f8fb;
}

.qrcode-box img {
  width: 128px;
  height: 128px;
  border-radius: 12px;
  object-fit: cover;
  background: #fff;
  border: 1px solid #e5e7ef;
}

.qrcode-box div {
  display: grid;
  gap: 8px;
}

.connection-list,
.message-list,
.current-detail {
  display: grid;
  gap: 8px;
}

.connection-row {
  width: 100%;
  justify-content: flex-start;
  min-height: 58px;
  border-radius: 14px;
  border: 1px solid #e8e4dc;
  background: #fff;
  color: #22252c;
  display: grid;
  grid-template-columns: 72px 1fr;
  text-align: left;
}

.connection-row.active {
  border-color: #5b5bf0;
  background: #f0f0ff;
}

.connection-row span {
  grid-row: span 2;
  color: #5b5bf0;
  font-size: 12px;
}

label {
  display: grid;
  gap: 7px;
  font-weight: 800;
}

select,
textarea {
  width: 100%;
  border: 1px solid #e0e3eb;
  border-radius: 14px;
  background: #fff;
  color: #22252c;
  font: inherit;
}

select {
  height: 42px;
  padding: 0 12px;
}

textarea {
  min-height: 150px;
  resize: vertical;
  padding: 12px;
  line-height: 1.55;
}

.current-detail {
  grid-template-columns: 88px 1fr;
  padding-top: 4px;
}

.current-detail span {
  color: #68707d;
}

.test-result,
.message-reply,
.message-user {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.6;
}

.test-result {
  padding: 12px;
  border-radius: 14px;
  background: #f2fbf5;
  border: 1px solid #d6efde;
}

.test-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.test-block {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid #eceef3;
  background: #fafafa;
}

.compact-textarea {
  min-height: 92px;
}

.monitor-list {
  max-height: min(260px, calc(100vh - 420px));
  overflow-y: auto;
  padding-right: 4px;
}

.message-item {
  display: grid;
  gap: 8px;
  padding: 13px;
  border-radius: 16px;
  background: #fafafa;
  border: 1px solid #eceef3;
}

.timeline-item.inbound {
  border-left: 4px solid #5b5bf0;
}

.timeline-item.outbound {
  border-left: 4px solid #1f9d66;
  background: #f7fcf9;
}

.message-meta {
  justify-content: space-between;
  gap: 10px;
  color: #68707d;
}

.message-meta span {
  color: #5b5bf0;
  font-weight: 800;
}

.message-user {
  padding: 10px;
  border-radius: 12px;
  background: #fff;
  max-height: 220px;
  overflow-y: auto;
  font-size: 14px;
}

.message-reply {
  padding: 10px;
  border-radius: 12px;
  background: #f1f0ff;
}

@media (max-width: 880px) {
  .wechat-page { padding: 20px; }
  .wechat-head { flex-direction: column; }
  .status-band,
  .wechat-grid {
    grid-template-columns: 1fr;
  }
  .connect-panel,
  .config-panel,
  .query-panel,
  .inbox-panel {
    grid-column: auto;
    grid-row: auto;
  }
  .test-grid {
    grid-template-columns: 1fr;
  }
}
</style>
