export type Sentiment = 'positive' | 'neutral' | 'negative'
export type ReactionType = 'like' | 'dislike' | 'question'
export type AccessMode = 'link_only' | 'login_required' | 'password_required'

export interface User {
  id: string
  email: string
  nickname: string
  is_admin: boolean
}

export interface Wall {
  id: string
  title: string
  description: string
  access_mode: AccessMode
  has_password: boolean
  canvas_height: number
  is_anonymous: boolean
  is_archived: boolean
  is_locked: boolean
  spotlight_card_id: string | null
  ai_enabled: boolean
  ai_model: 'deepseek-v4-flash' | 'deepseek-v4-pro'
  ai_thinking_enabled: boolean
  ai_reasoning_effort: 'high' | 'max'
  owner_id: string
  created_at: string
  updated_at: string
  card_count: number
}

export interface Card {
  id: string
  wall_id: string
  author_id: string
  author_name: string
  content_json: Record<string, unknown>
  plain_text: string
  x: number
  y: number
  width: number
  height: number
  color: string
  rotation: number
  z_index: number
  sentiment: Sentiment | null
  sentiment_confidence: number | null
  topic_labels: string[]
  reaction_counts: Record<ReactionType, number>
  own_reactions: ReactionType[]
  is_deleted: boolean
  created_at: string
  updated_at: string
}

export interface Placeholder {
  id: string
  wall_id: string
  user_id: string
  user_name: string
  x: number
  y: number
  color_hint: string
  created_at: string
  expires_at: string
  last_activity_at: string
}

export interface WallSnapshot {
  wall: Wall
  cards: Card[]
  online_users: Array<{ id: string; nickname: string }>
  placeholders: Placeholder[]
  requires_login?: boolean
  requires_password?: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface AuthEvent {
  id: string
  user_id: string | null
  email: string
  event_type: string
  ip_address: string
  user_agent: string
  created_at: string
}

export interface ResearchEventPayload {
  client_session_id: string
  client_event_id?: string
  event_type: string
  target_type?: string | null
  target_id?: string | null
  x?: number | null
  y?: number | null
  viewport_width?: number | null
  viewport_height?: number | null
  canvas_width?: number | null
  canvas_height?: number | null
  payload?: Record<string, unknown>
  client_ts?: string
}

export interface ResearchUserSummary {
  actor_id: string
  user_id: string | null
  user_name: string
  email: string | null
  is_registered: boolean
  client_session_ids: string[]
  card_count: number
  reaction_count: number
  action_count: number
  research_event_count: number
  event_count: number
  event_counts: Record<string, number>
  sentiment_counts: Record<'positive' | 'neutral' | 'negative' | 'unknown', number>
  average_card_text_length: number
  first_seen: string | null
  last_seen: string | null
  active_span_seconds: number
}

export interface ResearchSummary {
  exported_at: string
  wall_id: string
  wall_title: string
  user_count: number
  event_count: number
  users: ResearchUserSummary[]
}

export interface ResearchDashboardWall {
  id: string
  title: string
  description: string
  canvas_width: number
  canvas_height: number
}

export interface ResearchDashboardMetrics {
  participants: number
  cards: number
  reactions: number
  action_events: number
  behavior_events: number
  total_events: number
  started_at: string | null
  ended_at: string | null
  active_span_seconds: number
}

export interface ResearchDashboardCard {
  id: string
  author_id: string
  author_name: string
  plain_text: string
  x: number
  y: number
  width: number
  height: number
  sentiment: Sentiment | null
  reaction_count: number
  created_at: string | null
}

export interface ResearchDashboardPoint {
  id: string
  user_id: string | null
  user_name: string
  event_type: string
  target_type: string | null
  target_id: string | null
  x: number
  y: number
  weight: number
  created_at: string | null
}

export interface ResearchTimelineEvent {
  id: string
  source: string
  user_id: string | null
  user_name: string
  event_type: string
  target_type: string | null
  target_id: string | null
  x: number | null
  y: number | null
  plain_text: string
  payload: Record<string, unknown>
  created_at: string | null
  offset_seconds: number
}

export interface ResearchDashboard {
  exported_at: string
  wall: ResearchDashboardWall
  metrics: ResearchDashboardMetrics
  users: ResearchUserSummary[]
  cards: ResearchDashboardCard[]
  heatmap_points: ResearchDashboardPoint[]
  timeline: ResearchTimelineEvent[]
  event_rows: ResearchTimelineEvent[]
}

export interface WallAccessResponse {
  wall_access_token: string
  token_type: string
}

export interface SummaryEvidenceCard {
  id: string
  text: string
  sentiment: Sentiment | null
  reaction_count: number
}

export interface SummaryPoint {
  title: string
  summary: string
  evidence: SummaryEvidenceCard[]
}

export interface RiskPoint extends SummaryPoint {
  severity: 'low' | 'medium' | 'high' | string
}

export interface WallSummary {
  summary_id: string | null
  generated_at: string
  model: string
  thinking_enabled: boolean
  reasoning_effort: 'high' | 'max' | string
  cached: boolean
  cache_key: string | null
  card_count: number
  overview: string
  sentiment_counts: Record<'positive' | 'neutral' | 'negative' | 'unknown', number>
  key_points: SummaryPoint[]
  risks: RiskPoint[]
  representative_cards: SummaryEvidenceCard[]
}

export interface WallSummaryHistoryItem {
  id: string
  generated_at: string
  model: string
  thinking_enabled: boolean
  reasoning_effort: 'high' | 'max' | string
  card_count: number
  cache_key: string
  overview: string
}

export interface WallSummaryDiff {
  summary_id: string
  against_id: string
  generated_at: string
  against_generated_at: string
  card_count_delta: number
  sentiment_delta: Record<'positive' | 'neutral' | 'negative' | 'unknown', number>
  key_points_added: string[]
  key_points_removed: string[]
  risks_added: string[]
  risks_removed: string[]
  representative_cards_added: string[]
  representative_cards_removed: string[]
  overview_changed: boolean
}

export interface AiConnectionTest {
  status: string
  model: string
  thinking_enabled: boolean
  reasoning_effort: 'high' | 'max' | string
  latency_ms: number
  message: string
}

export interface SystemCheck {
  key: string
  label: string
  status: 'ok' | 'warning' | 'error'
  detail: string
}

export interface SystemStatus {
  status: 'ok' | 'warning' | 'error'
  checked_at: string
  checks: SystemCheck[]
}

export interface IntegrationRequirement {
  title: string
  detail: string
}

export interface IntegrationStatus {
  key: string
  label: string
  status: string
  enabled: boolean
  message: string
  planned_endpoint: string | null
  requirements: IntegrationRequirement[]
}

export interface WechatAssistantConnection {
  id: string
  owner_user_id: string
  provider: string
  status: string
  status_reason: string | null
  provider_account_id: string | null
  base_url: string | null
  last_cursor: string | null
  current_wall_id: string | null
  created_at: string
  updated_at: string
}

export interface WechatAssistantStatus {
  key: string
  label: string
  enabled: boolean
  status: string
  message: string
  provider: { kind: string; requires_production_secret: boolean }
  worker: { enabled: boolean; running: boolean; poll_interval_seconds: number }
  connection_count: number
  connected_count: number
  latest_connection: WechatAssistantConnection | null
  capabilities: string[]
  guardrails: string[]
}

export interface WechatAssistantQrcode {
  connection_id: string
  status: string
  qrcode_url: string
}

export interface WechatAssistantInboxItem {
  id: string
  connection_id: string
  external_message_id: string
  message_type: string
  text_content: string | null
  received_at: string
  processed_at: string | null
  ai_metadata: Record<string, unknown>
  reply: string | null
}

export interface WechatAssistantTimelineItem {
  id: string
  direction: 'inbound' | 'outbound'
  connection_id: string
  external_user_id: string
  message_type: string
  text_content: string | null
  delivery_policy: string | null
  delivery_status: string
  delivery_reason: string | null
  related_inbound_id: string | null
  ai_metadata: Record<string, unknown> | null
  timestamp: string
}

export interface WechatAssistantTestQueryResult {
  inbound_id: string
  reply: string | null
  metadata: Record<string, unknown>
}

export interface WechatAssistantTestSendResult {
  outbound_id: string
  external_user_id: string
  delivery_status: string
  delivery_reason: string | null
  provider_message_id: string | null
}
