import { defineStore } from 'pinia'
import { api, wsProtocols, wsUrl } from '../services/api'
import type { Card, Placeholder, ReactionType, ResearchEventPayload, Wall, WallSnapshot } from '../types'

interface DragPreview {
  card_id: string
  x: number
  y: number
}

function wallAccessKey(wallId: string): string {
  return `talon_wall_access_${wallId}`
}

const TRANSIENT_MOVE_INTERVAL_MS = 100
const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000]
let lastTransientSentAt = 0
let reconnectAttempt = 0
let reconnectTimer: number | undefined
let manualDisconnect = false

function clearReconnectTimer() {
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
  reconnectTimer = undefined
}

function nextReconnectDelay() {
  return RECONNECT_DELAYS_MS[Math.min(reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)]
}

export const useWallStore = defineStore('wall', {
  state: () => ({
    wall: null as Wall | null,
    cards: [] as Card[],
    placeholders: [] as Placeholder[],
    onlineUsers: [] as Array<{ id: string; nickname: string }>,
    socket: null as WebSocket | null,
    connected: false,
    requiresLogin: false,
    requiresPassword: false,
    dragPreview: null as DragPreview | null,
    spotlightCardId: null as string | null,
    lastCreatedCard: null as Card | null,
  }),
  getters: {
    sortedCards(state) {
      return [...state.cards].sort((a, b) => a.z_index - b.z_index)
    },
  },
  actions: {
    wallAccessToken(wallId: string) {
      return localStorage.getItem(wallAccessKey(wallId))
    },
    async load(wallId: string): Promise<WallSnapshot> {
      const snapshot = await api.wall(wallId, this.wallAccessToken(wallId))
      this.wall = snapshot.wall
      this.requiresLogin = Boolean(snapshot.requires_login)
      this.requiresPassword = Boolean(snapshot.requires_password)
      this.spotlightCardId = snapshot.wall.spotlight_card_id || null
      if (this.requiresLogin || this.requiresPassword) {
        if (this.requiresPassword) localStorage.removeItem(wallAccessKey(wallId))
        this.cards = []
        this.placeholders = []
        this.onlineUsers = []
        this.disconnect()
        return snapshot
      }
      this.cards = snapshot.cards
      this.placeholders = snapshot.placeholders || []
      this.onlineUsers = snapshot.online_users || []
      this.lastCreatedCard = null
      this.connect(wallId)
      return snapshot
    },
    async unlockWall(wallId: string, password: string) {
      const data = await api.unlockWall(wallId, password)
      localStorage.setItem(wallAccessKey(wallId), data.wall_access_token)
      this.requiresPassword = false
      return this.load(wallId)
    },
    disconnect() {
      manualDisconnect = true
      clearReconnectTimer()
      reconnectAttempt = 0
      lastTransientSentAt = 0
      if (this.socket) {
        this.socket.onclose = null
        this.socket.close()
      }
      this.socket = null
      this.connected = false
    },
    connect(wallId: string, reconnecting = false) {
      clearReconnectTimer()
      manualDisconnect = false
      if (!reconnecting) reconnectAttempt = 0
      lastTransientSentAt = 0
      if (this.socket) {
        this.socket.onclose = null
        this.socket.close()
      }
      this.socket = null
      this.connected = false
      const protocols = wsProtocols(this.wallAccessToken(wallId))
      const socket = protocols.length ? new WebSocket(wsUrl(wallId), protocols) : new WebSocket(wsUrl(wallId))
      socket.onopen = () => {
        if (this.socket !== socket) return
        this.connected = true
        reconnectAttempt = 0
      }
      socket.onclose = () => {
        if (this.socket !== socket) return
        this.connected = false
        this.socket = null
        if (manualDisconnect || this.wall?.id !== wallId || this.requiresLogin || this.requiresPassword) return
        const delay = nextReconnectDelay()
        reconnectAttempt += 1
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = undefined
          if (!manualDisconnect && this.wall?.id === wallId && !this.requiresLogin && !this.requiresPassword) {
            this.connect(wallId, true)
          }
        }, delay)
      }
      socket.onmessage = (event) => this.applyEvent(JSON.parse(event.data))
      this.socket = socket
    },
    applyEvent(event: { type: string; payload: any }) {
      if (event.type === 'wall:snapshot') {
        this.wall = event.payload.wall
        this.cards = event.payload.cards
        this.placeholders = event.payload.placeholders || []
        this.onlineUsers = event.payload.online_users || []
        this.spotlightCardId = event.payload.wall?.spotlight_card_id || null
      }
      if (event.type === 'presence:update') this.onlineUsers = event.payload
      if (['card:create', 'card:update', 'card:sentiment', 'card:move:commit', 'reaction:update'].includes(event.type)) {
        this.upsertCard(event.payload, { preserveOwnReactions: true })
      }
      if (event.type === 'card:create') {
        this.lastCreatedCard = event.payload
      }
      if (event.type === 'card:move:commit' && this.dragPreview?.card_id === event.payload.id) {
        this.dragPreview = null
      }
      if (event.type === 'card:delete') {
        this.cards = this.cards.filter((card) => card.id !== event.payload.card_id)
        if (this.dragPreview?.card_id === event.payload.card_id) this.dragPreview = null
        if (this.spotlightCardId === event.payload.card_id) this.spotlightCardId = null
      }
      if (event.type === 'placeholder:create' || event.type === 'placeholder:renew') {
        this.upsertPlaceholder(event.payload)
      }
      if (event.type === 'placeholder:remove') {
        this.placeholders = this.placeholders.filter((item) => item.id !== event.payload.id)
      }
      if (event.type === 'card:move:transient') {
        this.dragPreview = event.payload
      }
      if (event.type === 'wall:update') {
        this.wall = { ...(this.wall as Wall), ...event.payload }
      }
      if (event.type === 'wall:spotlight') {
        this.spotlightCardId = event.payload.card_id || null
      }
    },
    upsertCard(card: Card, options: { preserveOwnReactions?: boolean } = {}) {
      const idx = this.cards.findIndex((item) => item.id === card.id)
      if (idx >= 0) {
        const previous = this.cards[idx]
        this.cards[idx] = {
          ...card,
          own_reactions: options.preserveOwnReactions ? previous.own_reactions : card.own_reactions,
        }
      }
      else this.cards.push(card)
    },
    upsertPlaceholder(placeholder: Placeholder) {
      const idx = this.placeholders.findIndex((item) => item.id === placeholder.id)
      if (idx >= 0) this.placeholders[idx] = placeholder
      else this.placeholders.push(placeholder)
    },
    async createPlaceholder(payload: { x: number; y: number; canvas_width: number; color_hint?: string }) {
      if (!this.wall) return null
      const placeholder = await api.createPlaceholder(this.wall.id, payload, this.wallAccessToken(this.wall.id))
      this.upsertPlaceholder(placeholder)
      return placeholder
    },
    async renewPlaceholder(placeholderId: string) {
      if (!this.wall) return null
      const placeholder = await api.renewPlaceholder(this.wall.id, placeholderId, this.wallAccessToken(this.wall.id))
      this.upsertPlaceholder(placeholder)
      return placeholder
    },
    async releasePlaceholder(placeholderId: string) {
      if (!this.wall) return
      await api.releasePlaceholder(this.wall.id, placeholderId, this.wallAccessToken(this.wall.id))
      this.placeholders = this.placeholders.filter((item) => item.id !== placeholderId)
    },
    sendTransient(cardId: string, x: number, y: number) {
      if (this.socket?.readyState !== WebSocket.OPEN) return
      const now = Date.now()
      if (now - lastTransientSentAt < TRANSIENT_MOVE_INTERVAL_MS) return
      lastTransientSentAt = now
      this.socket.send(JSON.stringify({
        type: 'card:move:transient',
        payload: {
          card_id: cardId,
          x,
          y,
          client_event_id: `${cardId}:${now}`,
          sent_at: new Date(now).toISOString(),
        },
      }))
    },
    async createCard(payload: { content_json: Record<string, unknown>; plain_text: string; x: number; y: number; canvas_width?: number; color?: string; placeholder_id?: string }) {
      if (!this.wall) return null
      const card = await api.createCard(this.wall.id, payload, this.wallAccessToken(this.wall.id))
      this.upsertCard(card)
      return card
    },
    async moveCard(cardId: string, x: number, y: number, canvasWidth?: number) {
      if (!this.wall) return
      const card = await api.moveCard(this.wall.id, cardId, x, y, canvasWidth, this.wallAccessToken(this.wall.id))
      this.upsertCard(card)
    },
    async react(cardId: string, reactionType: ReactionType) {
      if (!this.wall) return
      const card = await api.react(this.wall.id, cardId, reactionType, this.wallAccessToken(this.wall.id))
      this.upsertCard(card)
    },
    async updateCard(cardId: string, payload: { content_json?: Record<string, unknown>; plain_text?: string }) {
      if (!this.wall) return null
      const card = await api.updateCard(this.wall.id, cardId, payload, this.wallAccessToken(this.wall.id))
      this.upsertCard(card)
      return card
    },
    async deleteCard(cardId: string) {
      if (!this.wall) return
      await api.deleteCard(this.wall.id, cardId, this.wallAccessToken(this.wall.id))
      this.cards = this.cards.filter((card) => card.id !== cardId)
    },
    async updateWall(payload: Partial<Wall>) {
      if (!this.wall) return null
      const wall = await api.updateWall(this.wall.id, payload)
      this.wall = wall
      return wall
    },
    async setSpotlight(cardId: string | null) {
      if (!this.wall) return
      const result = await api.setSpotlight(this.wall.id, cardId)
      this.spotlightCardId = result.card_id
    },
    async trackResearchEvents(events: ResearchEventPayload[]) {
      if (!this.wall || !events.length) return
      await api.trackResearchEvents(this.wall.id, events, this.wallAccessToken(this.wall.id))
    },
  },
})
