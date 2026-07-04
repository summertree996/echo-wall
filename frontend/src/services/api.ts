import type { AccessMode, AiConnectionTest, AuthEvent, AuthResponse, Card, IntegrationStatus, Placeholder, ReactionType, ResearchDashboard, ResearchEventPayload, ResearchSummary, SystemStatus, Wall, WallAccessResponse, WallSnapshot, WallSummary, WallSummaryDiff, WallSummaryHistoryItem, WechatAssistantConnection, WechatAssistantInboxItem, WechatAssistantQrcode, WechatAssistantStatus, WechatAssistantTestQueryResult, WechatAssistantTestSendResult, WechatAssistantTimelineItem } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const FIELD_LABELS: Record<string, string> = {
  email: '邮箱',
  password: '密码',
  nickname: '昵称',
}

function formatValidationMessage(issue: unknown): string | null {
  if (!issue || typeof issue !== 'object') return null
  const item = issue as { loc?: unknown; msg?: unknown; type?: unknown }
  const loc = Array.isArray(item.loc) ? item.loc.map(String) : []
  const field = loc[loc.length - 1] || ''
  const label = FIELD_LABELS[field] || field
  const msg = typeof item.msg === 'string' ? item.msg : ''
  const type = typeof item.type === 'string' ? item.type : ''

  if (field === 'email' || type.includes('email') || msg.toLowerCase().includes('email')) return '邮箱格式不正确'
  if (field === 'password' && (type.includes('too_short') || msg.includes('at least'))) return '密码至少 6 位'
  if (field === 'nickname' && (type.includes('too_short') || msg.includes('at least'))) return '请输入昵称'
  if (label && msg) return `${label}${msg.startsWith('Value error') ? '格式不正确' : `：${msg}`}`
  return msg || null
}

function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map(formatValidationMessage).filter((message): message is string => Boolean(message))
    return messages.length ? messages.join('；') : fallback
  }
  if (detail && typeof detail === 'object') {
    const item = detail as { message?: unknown; msg?: unknown; error?: unknown }
    if (typeof item.message === 'string') return item.message
    if (typeof item.msg === 'string') return item.msg
    if (typeof item.error === 'string') return item.error
  }
  return fallback
}

async function responseErrorMessage(res: Response): Promise<string> {
  let message = res.statusText
  try {
    const data = await res.json()
    message = formatApiDetail(data.detail, message)
  } catch {
    // keep status text
  }
  return message
}

function token(): string | null {
  return localStorage.getItem('talon_token')
}

function withWallAccess(options: RequestInit = {}, wallAccessToken?: string | null): RequestInit {
  if (!wallAccessToken) return options
  const headers = new Headers(options.headers)
  headers.set('X-Wall-Access-Token', wallAccessToken)
  return { ...options, headers }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  const accessToken = token()
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    throw new ApiError(res.status, await responseErrorMessage(res))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function requestBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const accessToken = token()
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const res = await fetch(`${API_BASE}${path}`, { headers })
  if (!res.ok) {
    throw new ApiError(res.status, await responseErrorMessage(res))
  }
  return res.blob()
}

export const api = {
  login(email: string, password: string) {
    return request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },
  register(email: string, password: string, nickname: string) {
    return request<AuthResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, nickname }),
    })
  },
  me() {
    return request<AuthResponse['user']>('/auth/me')
  },
  meActivity() {
    return request<{
      recent_activities: Array<{
        id: string
        wall_id: string
        wall_title: string
        excerpt: string
        created_at: string
        tone?: 'positive' | 'neutral' | 'question'
        tone_label?: string
        reply_count?: number
      }>
      recent_spaces: Array<{
        id: string
        title: string
        last_active_at: string
        role_in_space?: string
        latest_prompt?: string
        contribution_count?: number
        status?: 'active' | 'quiet' | 'ended'
      }>
    }>('/auth/me/activity')
  },
  logout() {
    return request<void>('/auth/logout', { method: 'POST' })
  },
  authEvents(filters: { event_type?: string; email?: string } = {}) {
    const params = new URLSearchParams()
    if (filters.event_type) params.set('event_type', filters.event_type)
    if (filters.email) params.set('email', filters.email)
    const query = params.toString()
    return request<AuthEvent[]>(`/auth/events${query ? `?${query}` : ''}`)
  },
  systemStatus() {
    return request<SystemStatus>('/system/status')
  },
  wechatIntegrationStatus() {
    return request<IntegrationStatus>('/integrations/wechat/status')
  },
  wechatAssistantStatus() {
    return request<WechatAssistantStatus>('/wechat-assistant/status')
  },
  wechatAssistantConnections() {
    return request<WechatAssistantConnection[]>('/wechat-assistant/connections')
  },
  requestWechatAssistantQrcode() {
    return request<WechatAssistantQrcode>('/wechat-assistant/connections/request-qrcode', { method: 'POST' })
  },
  pollWechatAssistantQrcode(connectionId: string) {
    return request<WechatAssistantConnection & { provider_status?: string }>('/wechat-assistant/connections/poll-qrcode-status', {
      method: 'POST',
      body: JSON.stringify({ connection_id: connectionId }),
    })
  },
  mockConfirmWechatAssistant(connectionId: string) {
    return request<WechatAssistantConnection>(`/wechat-assistant/connections/${connectionId}/mock-confirm`, { method: 'POST' })
  },
  setWechatAssistantCurrentWall(connectionId: string, wallId: string | null) {
    return request<WechatAssistantConnection>(`/wechat-assistant/connections/${connectionId}/current-wall`, {
      method: 'PATCH',
      body: JSON.stringify({ wall_id: wallId }),
    })
  },
  testWechatAssistantQuery(connectionId: string, payload: { text: string; wall_id?: string | null }) {
    return request<WechatAssistantTestQueryResult>(`/wechat-assistant/connections/${connectionId}/test-ai-query`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  testWechatAssistantSend(connectionId: string, payload: { text: string; external_user_id?: string | null }) {
    return request<WechatAssistantTestSendResult>(`/wechat-assistant/connections/${connectionId}/test-send`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  wechatAssistantInbox(limit = 30) {
    return request<WechatAssistantInboxItem[]>(`/wechat-assistant/messages/inbox?limit=${limit}`)
  },
  wechatAssistantTimeline(limit = 80, connectionId?: string) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (connectionId) params.set('connection_id', connectionId)
    return request<WechatAssistantTimelineItem[]>(`/wechat-assistant/messages/timeline?${params.toString()}`)
  },
  pollWechatAssistantOnce(connectionId: string) {
    return request<{ processed: number; inbound_ids: string[] }>(`/wechat-assistant/connections/${connectionId}/poll-once`, { method: 'POST' })
  },
  adminWalls() {
    return request<Wall[]>('/walls/admin')
  },
  createWall(payload: Partial<Wall> & { title: string; description: string; access_mode: AccessMode; password?: string }) {
    return request<Wall>('/walls', { method: 'POST', body: JSON.stringify(payload) })
  },
  updateWall(wallId: string, payload: Partial<Pick<Wall, 'title' | 'description' | 'access_mode' | 'is_anonymous' | 'is_archived' | 'is_locked' | 'ai_enabled' | 'ai_model' | 'ai_thinking_enabled' | 'ai_reasoning_effort'>> & { password?: string }) {
    return request<Wall>(`/walls/${wallId}`, { method: 'PATCH', body: JSON.stringify(payload) })
  },
  exportWall(wallId: string) {
    return request<unknown>(`/walls/${wallId}/export`)
  },
  exportWallCsv(wallId: string) {
    return requestBlob(`/walls/${wallId}/export.csv`)
  },
  exportWallActionsCsv(wallId: string) {
    return requestBlob(`/walls/${wallId}/export.actions.csv`)
  },
  researchSummary(wallId: string) {
    return request<ResearchSummary>(`/walls/${wallId}/research/summary`)
  },
  researchDashboard(wallId: string) {
    return request<ResearchDashboard>(`/walls/${wallId}/research/dashboard`)
  },
  exportResearchCsv(wallId: string) {
    return requestBlob(`/walls/${wallId}/research/export.csv`)
  },
  exportResearchUserCsv(wallId: string, userId: string) {
    return requestBlob(`/walls/${wallId}/research/users/${userId}/export.csv`)
  },
  trackResearchEvents(wallId: string, events: ResearchEventPayload[], wallAccessToken?: string | null) {
    return request<{ accepted: number }>(
      `/walls/${wallId}/research/events`,
      withWallAccess({ method: 'POST', body: JSON.stringify({ events }) }, wallAccessToken),
    )
  },
  wall(wallId: string, wallAccessToken?: string | null) {
    return request<WallSnapshot>(`/walls/${wallId}`, withWallAccess({}, wallAccessToken))
  },
  unlockWall(wallId: string, password: string) {
    return request<WallAccessResponse>(`/walls/${wallId}/access`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
  },
  wallSummary(wallId: string, refresh = false) {
    return request<WallSummary>(`/walls/${wallId}/ai/summary${refresh ? '?refresh=true' : ''}`, { method: 'POST' })
  },
  testWallAi(wallId: string, payload: Pick<Wall, 'ai_model' | 'ai_thinking_enabled' | 'ai_reasoning_effort'>) {
    return request<AiConnectionTest>(`/walls/${wallId}/ai/test`, { method: 'POST', body: JSON.stringify(payload) })
  },
  wallSummaryHistory(wallId: string) {
    return request<WallSummaryHistoryItem[]>(`/walls/${wallId}/ai/summary/history`)
  },
  wallSummaryHistoryItem(wallId: string, summaryId: string) {
    return request<WallSummary>(`/walls/${wallId}/ai/summary/history/${summaryId}`)
  },
  wallSummaryDiff(wallId: string, summaryId: string) {
    return request<WallSummaryDiff>(`/walls/${wallId}/ai/summary/history/${summaryId}/diff`)
  },
  setSpotlight(wallId: string, cardId: string | null) {
    return request<{ card_id: string | null }>(`/walls/${wallId}/spotlight`, {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId }),
    })
  },
  createPlaceholder(wallId: string, payload: { x: number; y: number; canvas_width: number; color_hint?: string }, wallAccessToken?: string | null) {
    return request<Placeholder>(`/walls/${wallId}/placeholders`, withWallAccess({ method: 'POST', body: JSON.stringify(payload) }, wallAccessToken))
  },
  renewPlaceholder(wallId: string, placeholderId: string, wallAccessToken?: string | null) {
    return request<Placeholder>(`/walls/${wallId}/placeholders/${placeholderId}`, withWallAccess({ method: 'PATCH', body: JSON.stringify({ typing: true }) }, wallAccessToken))
  },
  releasePlaceholder(wallId: string, placeholderId: string, wallAccessToken?: string | null) {
    return request<void>(`/walls/${wallId}/placeholders/${placeholderId}`, withWallAccess({ method: 'DELETE' }, wallAccessToken))
  },
  createCard(wallId: string, payload: { content_json: Record<string, unknown>; plain_text: string; x: number; y: number; canvas_width?: number; color?: string; placeholder_id?: string }, wallAccessToken?: string | null) {
    return request<Card>(`/walls/${wallId}/cards`, withWallAccess({ method: 'POST', body: JSON.stringify(payload) }, wallAccessToken))
  },
  moveCard(wallId: string, cardId: string, x: number, y: number, canvasWidth?: number, wallAccessToken?: string | null) {
    return request<Card>(`/walls/${wallId}/cards/${cardId}/move`, withWallAccess({ method: 'POST', body: JSON.stringify({ x, y, canvas_width: canvasWidth }) }, wallAccessToken))
  },
  updateCard(wallId: string, cardId: string, payload: { content_json?: Record<string, unknown>; plain_text?: string }, wallAccessToken?: string | null) {
    return request<Card>(`/walls/${wallId}/cards/${cardId}`, withWallAccess({ method: 'PATCH', body: JSON.stringify(payload) }, wallAccessToken))
  },
  deleteCard(wallId: string, cardId: string, wallAccessToken?: string | null) {
    return request<void>(`/walls/${wallId}/cards/${cardId}`, withWallAccess({ method: 'DELETE' }, wallAccessToken))
  },
  react(wallId: string, cardId: string, reaction_type: ReactionType, wallAccessToken?: string | null) {
    return request<Card>(`/walls/${wallId}/cards/${cardId}/reactions`, withWallAccess({ method: 'POST', body: JSON.stringify({ reaction_type }) }, wallAccessToken))
  },
}

export function wsUrl(wallId: string): string {
  const defaultBase = window.location.protocol === 'https:' ? `wss://${window.location.host}` : `ws://${window.location.host}`
  const base = (import.meta.env.VITE_WS_BASE || defaultBase).replace(/\/$/, '')
  return `${base}/ws/walls/${wallId}`
}

export function wsProtocols(wallAccessToken?: string | null): string[] {
  const accessToken = token()
  const protocols: string[] = ['talon']
  if (accessToken) protocols.push(`talon.auth.${accessToken}`)
  if (wallAccessToken) protocols.push(`talon.wall.${wallAccessToken}`)
  return protocols
}
