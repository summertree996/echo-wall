<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  ChevronLeft,
  ChevronRight,
  Clock3,
  Crown,
  LogIn,
  LogOut,
  MapPin,
  MessageSquareText,
  PencilLine,
  StickyNote,
  UserRound,
  X,
} from '@lucide/vue'
import type { Card, User, WallSnapshot } from '../types'

type PresenceStatus = 'online' | 'recent'

interface RailMember {
  id: string
  nickname: string
  email?: string
  isCurrent: boolean
  isAdmin: boolean
  status: PresenceStatus
}

const MEMBER_LIMIT = 8
const DEMO_MEMBER_TARGET = 5
const AVATAR_GRADIENTS = [
  ['#1f7a8c', '#72ddf7'],
  ['#7f4f24', '#ffb703'],
  ['#3a5a40', '#95d5b2'],
  ['#5a189a', '#f15bb5'],
  ['#0f4c5c', '#e36414'],
  ['#335c67', '#fff3b0'],
  ['#6d597a', '#eaac8b'],
  ['#2b2d42', '#8d99ae'],
]

const props = defineProps<{
  users: WallSnapshot['online_users']
  anonymous: boolean
  currentUser: User | null
  isAdmin: boolean
  ownCardCount: number
  cards: Card[]
  connected: boolean
  wallOwnerId?: string | null
}>()

const emit = defineEmits<{
  login: []
  logout: []
  showMine: []
  'locate-card': [cardId: string]
}>()

const railRef = ref<HTMLElement | null>(null)
const profileOpen = ref(false)
const selectedMemberId = ref<string | null>(null)
const selectedCardIndex = ref(0)
const showAllMembers = ref(false)
const seenOrder = ref<Record<string, number>>({})
let nextSeenOrder = 0

function rememberUser(id: string | null | undefined) {
  if (!id || seenOrder.value[id] !== undefined) return
  seenOrder.value[id] = nextSeenOrder
  nextSeenOrder += 1
}

watch(
  () => [
    props.currentUser?.id || '',
    ...props.users.map((user) => user.id),
    ...props.cards.map((card) => card.author_id),
  ].join('|'),
  () => {
    if (props.connected) rememberUser(props.currentUser?.id)
    props.users.forEach((user) => rememberUser(user.id))
    props.cards.forEach((card) => rememberUser(card.author_id))
  },
  { immediate: true },
)

const cardsByAuthor = computed(() => {
  const grouped = new Map<string, Card[]>()
  props.cards
    .filter((card) => !card.is_deleted)
    .forEach((card) => {
      const list = grouped.get(card.author_id) || []
      list.push(card)
      grouped.set(card.author_id, list)
    })

  grouped.forEach((cards) => {
    cards.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  })
  return grouped
})

const ownCards = computed(() => props.currentUser ? cardsByAuthor.value.get(props.currentUser.id) || [] : [])
const ownRecentCards = computed(() => ownCards.value.slice(0, 3))

const members = computed(() => {
  const byId = new Map<string, RailMember>()

  props.users.forEach((user) => {
    byId.set(user.id, {
      id: user.id,
      nickname: user.nickname,
      isCurrent: user.id === props.currentUser?.id,
      isAdmin: user.id === props.currentUser?.id && props.isAdmin,
      status: 'online',
    })
  })

  if (props.currentUser && props.connected) {
    const existing = byId.get(props.currentUser.id)
    byId.set(props.currentUser.id, {
      ...existing,
      id: props.currentUser.id,
      nickname: props.currentUser.nickname,
      email: props.currentUser.email,
      isCurrent: true,
      isAdmin: props.isAdmin,
      status: 'online',
    })
  }

  if (byId.size < DEMO_MEMBER_TARGET) {
    const recentAuthors = [...cardsByAuthor.value.entries()]
      .sort((a, b) => {
        const latestA = new Date(a[1][0]?.created_at || 0).getTime()
        const latestB = new Date(b[1][0]?.created_at || 0).getTime()
        return latestB - latestA
      })

    for (const [authorId, cards] of recentAuthors) {
      if (byId.size >= DEMO_MEMBER_TARGET) break
      if (byId.has(authorId)) continue
      byId.set(authorId, {
        id: authorId,
        nickname: cards[0]?.author_name || '成员',
        isCurrent: authorId === props.currentUser?.id,
        isAdmin: authorId === props.currentUser?.id && props.isAdmin,
        status: 'recent',
      })
    }
  }

  return [...byId.values()].sort((a, b) => {
    const hostDelta = Number(!isHost(a)) - Number(!isHost(b))
    if (hostDelta) return hostDelta
    const statusDelta = Number(a.status !== 'online') - Number(b.status !== 'online')
    if (statusDelta) return statusDelta
    return orderFor(a.id) - orderFor(b.id)
  })
})

const visibleMembers = computed(() => showAllMembers.value ? members.value : members.value.slice(0, MEMBER_LIMIT))
const overflowCount = computed(() => Math.max(0, members.value.length - visibleMembers.value.length))
const onlineCount = computed(() => members.value.filter((member) => member.status === 'online').length)
const selectedMember = computed(() => members.value.find((member) => member.id === selectedMemberId.value) || null)
const selectedMemberCards = computed(() => selectedMember.value ? cardsByAuthor.value.get(selectedMember.value.id) || [] : [])
const selectedCard = computed(() => selectedMemberCards.value[selectedCardIndex.value] || null)
const selectedMemberPopoverStyle = computed(() => {
  const selectedIndex = Math.max(0, visibleMembers.value.findIndex((member) => member.id === selectedMember.value?.id))
  return { top: `${74 + selectedIndex * 54}px` }
})

watch(() => selectedMemberCards.value.length, (length) => {
  if (selectedCardIndex.value < length) return
  selectedCardIndex.value = Math.max(0, length - 1)
})

function orderFor(id: string) {
  return seenOrder.value[id] ?? Number.MAX_SAFE_INTEGER
}

function isHost(member: RailMember) {
  return member.isAdmin || member.id === props.wallOwnerId
}

function roleLabel(member: RailMember) {
  return isHost(member) ? '主持人' : '成员'
}

function presenceLabel(member: RailMember) {
  return member.status === 'online' ? '实时在线' : '近期活跃'
}

function displayName(member: RailMember) {
  if (props.anonymous && !member.isCurrent) return '匿名成员'
  return member.nickname || '成员'
}

function avatarInitial(member: RailMember | User) {
  const source = 'isCurrent' in member ? displayName(member) : member.nickname
  return (source || '成').trim().slice(0, 1).toUpperCase()
}

function hashText(text: string) {
  let hash = 0
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 31 + text.charCodeAt(index)) >>> 0
  }
  return hash
}

function avatarStyle(member: RailMember | User) {
  const key = 'isCurrent' in member
    ? `${member.id}:${member.email || member.nickname}`
    : `${member.id}:${member.email}:${member.nickname}`
  const hash = hashText(key)
  const [from, to] = AVATAR_GRADIENTS[hash % AVATAR_GRADIENTS.length]
  const angle = 120 + (hash % 80)
  return {
    background: `radial-gradient(circle at 28% 24%, rgba(255,255,255,0.55), transparent 22%), linear-gradient(${angle}deg, ${from}, ${to})`,
  }
}

function formatRelativeTime(value: string | undefined) {
  if (!value) return '暂无发言'
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return '时间未知'
  const diff = Date.now() - timestamp
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.max(1, Math.round(diff / 60_000))} 分钟前`
  if (diff < 86_400_000) return `${Math.max(1, Math.round(diff / 3_600_000))} 小时前`
  if (diff < 604_800_000) return `${Math.max(1, Math.round(diff / 86_400_000))} 天前`
  return new Date(value).toLocaleDateString([], { month: 'numeric', day: 'numeric' })
}

function shortText(text: string) {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (!normalized) return '空白发言'
  return normalized.length > 42 ? `${normalized.slice(0, 42)}...` : normalized
}

function openMember(member: RailMember) {
  if (member.isCurrent) {
    toggleProfile()
    return
  }
  profileOpen.value = false
  selectedMemberId.value = selectedMemberId.value === member.id ? null : member.id
  selectedCardIndex.value = 0
}

function toggleProfile() {
  if (!props.currentUser) return
  selectedMemberId.value = null
  profileOpen.value = !profileOpen.value
}

function closePanels() {
  selectedMemberId.value = null
  profileOpen.value = false
}

function locateCard(cardId: string | undefined) {
  if (!cardId) return
  emit('locate-card', cardId)
}

function locateSelectedCard() {
  locateCard(selectedCard.value?.id)
}

function moveSelectedCard(delta: number) {
  const cards = selectedMemberCards.value
  if (!cards.length) return
  selectedCardIndex.value = (selectedCardIndex.value + delta + cards.length) % cards.length
  locateSelectedCard()
}

function showMine() {
  emit('showMine')
  profileOpen.value = false
}

function logout() {
  closePanels()
  emit('logout')
}

function handleOutsidePointer(event: PointerEvent) {
  const target = event.target
  if (!(target instanceof Node)) return
  if (railRef.value?.contains(target)) return
  closePanels()
}

onMounted(() => {
  document.addEventListener('pointerdown', handleOutsidePointer)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', handleOutsidePointer)
})
</script>

<template>
  <aside ref="railRef" class="online-rail">
    <div class="rail-logo logo-mini" aria-hidden="true"><StickyNote :size="20" /></div>

    <section class="rail-members" aria-label="在线成员">
      <div class="rail-section-head">
        <span>在线</span>
        <b>{{ onlineCount }}</b>
      </div>

      <div class="online-list" role="list">
        <button
          v-for="member in visibleMembers"
          :key="member.id"
          class="member-button"
          :class="{ active: selectedMemberId === member.id, muted: member.status !== 'online' }"
          type="button"
          :aria-label="`${displayName(member)}，${roleLabel(member)}，${presenceLabel(member)}`"
          @click="openMember(member)"
        >
          <span class="rail-avatar" :style="avatarStyle(member)">
            <span>{{ avatarInitial(member) }}</span>
            <Crown v-if="isHost(member)" class="host-crown" :size="13" />
            <i class="presence-dot" :class="member.status"></i>
          </span>
          <small>{{ displayName(member) }}</small>
        </button>

        <button v-if="overflowCount" class="overflow-member" type="button" @click="showAllMembers = true">
          +{{ overflowCount }}
        </button>
      </div>
    </section>

    <div v-if="selectedMember" class="member-popover" :style="selectedMemberPopoverStyle">
      <header>
        <span class="rail-avatar large" :style="avatarStyle(selectedMember)">{{ avatarInitial(selectedMember) }}</span>
        <div>
          <b>{{ displayName(selectedMember) }}</b>
          <small>{{ roleLabel(selectedMember) }} · {{ presenceLabel(selectedMember) }}</small>
        </div>
        <button class="icon-button" type="button" aria-label="关闭成员卡片" @click="selectedMemberId = null"><X :size="15" /></button>
      </header>

      <div class="member-stats">
        <span>
          <b>{{ selectedMemberCards.length }}</b>
          发言
        </span>
        <span>
          <Clock3 :size="14" />
          {{ formatRelativeTime(selectedMemberCards[0]?.created_at) }}
        </span>
      </div>

      <template v-if="!anonymous || selectedMember.isCurrent">
        <section class="recent-section">
          <div class="section-title"><MessageSquareText :size="14" />最近发言</div>
          <button
            v-for="card in selectedMemberCards.slice(0, 3)"
            :key="card.id"
            class="recent-card-button"
            type="button"
            @click="locateCard(card.id)"
          >
            <span>{{ shortText(card.plain_text) }}</span>
            <small>{{ formatRelativeTime(card.created_at) }}</small>
          </button>
          <p v-if="!selectedMemberCards.length" class="empty-copy">暂无发言</p>
        </section>

        <div class="locate-row">
          <button class="locate-main" type="button" :disabled="!selectedCard" @click="locateSelectedCard">
            <MapPin :size="15" />
            定位最新发言
          </button>
          <button class="icon-button" type="button" :disabled="selectedMemberCards.length < 2" aria-label="上一条发言" @click="moveSelectedCard(1)">
            <ChevronLeft :size="15" />
          </button>
          <button class="icon-button" type="button" :disabled="selectedMemberCards.length < 2" aria-label="下一条发言" @click="moveSelectedCard(-1)">
            <ChevronRight :size="15" />
          </button>
        </div>
        <small v-if="selectedMemberCards.length > 1" class="card-index">{{ selectedCardIndex + 1 }} / {{ selectedMemberCards.length }}</small>
      </template>

      <p v-else class="empty-copy">匿名模式下不展示成员发言明细</p>
    </div>

    <div class="current-user-slot">
      <div v-if="currentUser" class="rail-current-card" :class="{ open: profileOpen }">
        <button class="rail-current-trigger" type="button" :aria-expanded="profileOpen" @click="toggleProfile">
          <span class="rail-avatar self" :style="avatarStyle(currentUser)">{{ avatarInitial(currentUser) }}</span>
          <span class="current-summary">
            <small>我</small>
            <b>{{ currentUser.nickname }}</b>
            <em>{{ isAdmin ? '主持人' : '成员' }}</em>
          </span>
        </button>
        <button class="current-logout" type="button" title="退出登录" @click.stop="logout"><LogOut :size="15" /></button>
      </div>

      <button v-else class="rail-login" type="button" @click="$emit('login')">
        <LogIn :size="16" />
        <span>登录</span>
      </button>
    </div>

    <button v-if="profileOpen" class="drawer-scrim" type="button" aria-label="关闭个人抽屉" @click="profileOpen = false"></button>

    <aside v-if="profileOpen && currentUser" class="profile-drawer" aria-label="当前用户">
      <header>
        <div class="profile-title">
          <span class="rail-avatar xl" :style="avatarStyle(currentUser)">{{ avatarInitial(currentUser) }}</span>
          <div>
            <small>当前用户</small>
            <h2>{{ currentUser.nickname }}</h2>
            <p>{{ currentUser.email }}</p>
          </div>
        </div>
        <button class="icon-button" type="button" aria-label="关闭个人抽屉" @click="profileOpen = false"><X :size="16" /></button>
      </header>

      <div class="profile-meta">
        <span><UserRound :size="15" />{{ isAdmin ? '主持人账号' : '参与者账号' }}</span>
        <span><MessageSquareText :size="15" />我的发言 {{ ownCardCount }}</span>
      </div>

      <RouterLink class="drawer-profile-link" :to="{ name: 'me' }" @click="profileOpen = false">
        <UserRound :size="16" />
        <span>
          <b>个人页</b>
          <small>查看自己的发言和参与记录</small>
        </span>
      </RouterLink>

      <section class="drawer-section">
        <div class="drawer-section-title">
          <b>最近发言</b>
          <button type="button" :disabled="!ownRecentCards.length" @click="showMine">
            <MapPin :size="14" />
            定位最新
          </button>
        </div>
        <button
          v-for="card in ownRecentCards"
          :key="card.id"
          class="drawer-card-row"
          type="button"
          @click="locateCard(card.id)"
        >
          <span>{{ shortText(card.plain_text) }}</span>
          <small>{{ formatRelativeTime(card.created_at) }}</small>
        </button>
        <p v-if="!ownRecentCards.length" class="empty-copy">你还没有发言</p>
      </section>

      <button class="profile-placeholder" type="button" aria-disabled="true">
        <PencilLine :size="16" />
        <span>
          <b>修改昵称</b>
          <small>暂未开放</small>
        </span>
      </button>

      <button class="drawer-logout" type="button" @click="logout">
        <LogOut :size="16" />
        退出登录
      </button>
    </aside>
  </aside>
</template>

<style scoped>
.online-rail {
  position: relative;
  z-index: 80;
  align-items: stretch;
  overflow: visible;
  isolation: isolate;
}

.rail-logo {
  align-self: center;
  flex: 0 0 auto;
}

.rail-members {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 8px;
  min-height: 0;
  flex: 1;
}

.rail-section-head {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  color: var(--ink-3);
  font-size: 11px;
  font-weight: 800;
}

.rail-section-head b {
  min-width: 18px;
  height: 18px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(20, 22, 28, 0.08);
  color: var(--ink-2);
  font-size: 10px;
}

.online-list {
  width: 100%;
  align-items: center;
  gap: 8px;
  overflow-y: auto;
  overflow-x: visible;
  padding: 2px 0 6px;
  scrollbar-width: none;
}

.online-list::-webkit-scrollbar {
  display: none;
}

.member-button {
  width: 64px;
  display: grid;
  justify-items: center;
  gap: 4px;
  border: none;
  border-radius: 14px;
  padding: 4px 3px 5px;
  background: transparent;
  color: var(--ink-2);
}

.member-button:hover,
.member-button.active {
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 8px 22px rgba(28, 30, 45, 0.09);
}

.member-button.muted {
  opacity: 0.78;
}

.member-button small {
  width: 58px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
  font-weight: 800;
  line-height: 1.1;
}

.rail-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: white;
  font-size: 15px;
  font-weight: 900;
  line-height: 1;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.32),
    0 0 0 3px rgba(255, 255, 255, 0.82),
    0 10px 20px rgba(28, 30, 45, 0.13);
}

.rail-avatar.self {
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.38),
    0 0 0 4px rgba(255, 255, 255, 0.9),
    0 12px 24px rgba(28, 30, 45, 0.16);
}

.rail-avatar.large {
  width: 46px;
  height: 46px;
  font-size: 17px;
}

.rail-avatar.xl {
  width: 58px;
  height: 58px;
  font-size: 21px;
}

.host-crown {
  position: absolute;
  top: -5px;
  right: -5px;
  padding: 2px;
  border-radius: 50%;
  background: #fff8db;
  color: #9a6b00;
  box-shadow: 0 2px 8px rgba(28, 30, 45, 0.14);
}

.presence-dot {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid #fff;
  background: var(--neu);
}

.presence-dot.online {
  background: var(--pos);
}

.presence-dot.recent {
  background: #f0b54a;
}

.overflow-member {
  width: 42px;
  min-height: 30px;
  border: none;
  border-radius: 999px;
  background: rgba(20, 22, 28, 0.08);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 900;
}

.member-popover,
.profile-drawer {
  color: var(--ink);
  border: 1px solid rgba(255, 255, 255, 0.78);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 70px rgba(28, 30, 45, 0.18);
  backdrop-filter: blur(18px);
}

.member-popover {
  position: absolute;
  left: calc(100% + 10px);
  z-index: 90;
  width: 294px;
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
}

.member-popover header,
.profile-drawer header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.member-popover header > div,
.profile-title > div {
  min-width: 0;
  flex: 1;
}

.member-popover b,
.profile-drawer h2,
.profile-title b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-popover header b {
  display: block;
  font-size: 15px;
}

.member-popover header small,
.profile-title small,
.profile-title p,
.recent-card-button small,
.drawer-card-row small,
.card-index,
.empty-copy {
  color: var(--ink-3);
}

.icon-button {
  flex: 0 0 auto;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  padding: 0;
  background: rgba(20, 22, 28, 0.06);
  color: var(--ink-2);
}

.icon-button:disabled,
.locate-main:disabled,
.drawer-section-title button:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.member-stats,
.profile-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.member-stats span,
.profile-meta span {
  min-width: 0;
  display: grid;
  gap: 4px;
  border-radius: 12px;
  padding: 9px 10px;
  background: #f5f6f9;
  color: var(--ink-2);
  font-size: 12px;
}

.member-stats b {
  color: var(--ink);
  font-size: 17px;
}

.profile-meta span {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 800;
}

.recent-section,
.drawer-section {
  display: grid;
  gap: 8px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 900;
}

.recent-card-button,
.drawer-card-row {
  width: 100%;
  min-width: 0;
  display: grid;
  gap: 4px;
  border: none;
  border-radius: 12px;
  padding: 9px 10px;
  text-align: left;
  background: #f7f8fb;
  color: var(--ink);
}

.recent-card-button:hover,
.drawer-card-row:hover {
  background: var(--accent-soft);
}

.recent-card-button span,
.drawer-card-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
}

.recent-card-button small,
.drawer-card-row small {
  font-size: 11px;
}

.locate-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
}

.locate-main,
.drawer-section-title button,
.drawer-logout {
  border: none;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 11px;
  font-size: 12px;
  font-weight: 900;
}

.locate-main,
.drawer-section-title button {
  background: var(--accent-soft);
  color: var(--accent);
}

.card-index {
  justify-self: end;
  font-size: 11px;
}

.current-user-slot {
  z-index: 1;
}

.rail-current-card {
  display: grid;
  justify-items: center;
  gap: 8px;
  padding: 10px 6px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 14px 34px rgba(28, 30, 45, 0.1);
}

.rail-current-card.open {
  box-shadow: 0 0 0 2px rgba(91, 91, 240, 0.14), 0 16px 36px rgba(28, 30, 45, 0.14);
}

.rail-current-trigger {
  min-width: 0;
  display: grid;
  justify-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: inherit;
  padding: 0;
}

.current-summary {
  min-width: 0;
  display: grid;
  justify-items: center;
  gap: 2px;
}

.current-summary small {
  color: var(--ink-3);
  font-size: 10px;
}

.current-summary b {
  max-width: 62px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.current-summary em {
  border-radius: 999px;
  background: #f1f2f6;
  color: var(--ink-2);
  padding: 3px 7px;
  font-size: 10px;
  font-style: normal;
  font-weight: 900;
}

.current-logout {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  padding: 0;
  background: rgba(20, 22, 28, 0.06);
  color: var(--ink-2);
}

.rail-login {
  width: 100%;
  min-height: 38px;
  border: none;
  border-radius: 999px;
  background: rgba(20, 22, 28, 0.07);
  color: var(--ink-2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-weight: 900;
}

.drawer-scrim {
  position: fixed;
  inset: 0;
  z-index: 84;
  border: none;
  background: transparent;
}

.profile-drawer {
  position: fixed;
  left: 98px;
  top: 16px;
  bottom: 16px;
  z-index: 95;
  width: min(340px, calc(100vw - 116px));
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  border-radius: 22px;
}

.profile-drawer header {
  align-items: flex-start;
}

.profile-title {
  min-width: 0;
  display: flex;
  gap: 13px;
  align-items: center;
}

.profile-title h2 {
  margin: 3px 0 2px;
  font-size: 20px;
  line-height: 1.15;
}

.profile-title p {
  max-width: 210px;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.drawer-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.drawer-section-title b {
  font-size: 14px;
}

.profile-placeholder {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px dashed rgba(91, 91, 240, 0.26);
  border-radius: 14px;
  padding: 12px;
  text-align: left;
  background: rgba(91, 91, 240, 0.06);
  color: var(--ink-2);
  cursor: default;
}

.drawer-profile-link {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 14px;
  padding: 12px;
  background: var(--brand);
  color: #fff;
  text-align: left;
  text-decoration: none;
  box-shadow: 0 12px 28px rgba(28, 30, 45, 0.14);
}

.drawer-profile-link span {
  display: grid;
  gap: 2px;
}

.drawer-profile-link b {
  font-size: 13px;
}

.drawer-profile-link small {
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
}

.profile-placeholder span {
  display: grid;
  gap: 2px;
}

.profile-placeholder b {
  color: var(--ink);
  font-size: 13px;
}

.profile-placeholder small {
  color: var(--ink-3);
  font-size: 12px;
}

.drawer-logout {
  margin-top: auto;
  width: 100%;
  background: rgba(239, 95, 87, 0.1);
  color: #c84339;
}

.empty-copy {
  margin: 0;
  border-radius: 12px;
  background: #f7f8fb;
  padding: 10px;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .online-rail {
    align-items: center;
    overflow-x: auto;
    overflow-y: visible;
  }

  .rail-members {
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-rows: auto;
    align-items: center;
    min-width: 0;
  }

  .rail-section-head {
    min-width: 44px;
  }

  .online-list {
    width: auto;
    min-width: 0;
    flex-direction: row;
    overflow-x: auto;
    overflow-y: visible;
    padding: 0 4px;
  }

  .member-button {
    width: 48px;
    padding: 3px 2px;
  }

  .member-button small {
    display: none;
  }

  .rail-avatar {
    width: 34px;
    height: 34px;
    font-size: 13px;
  }

  .rail-avatar.large {
    width: 42px;
    height: 42px;
  }

  .rail-current-card {
    grid-template-columns: auto auto;
    grid-auto-flow: column;
    align-items: center;
    padding: 7px 8px;
  }

  .rail-current-trigger {
    grid-template-columns: auto auto;
    align-items: center;
    justify-items: start;
  }

  .current-summary {
    justify-items: start;
  }

  .member-popover {
    position: fixed;
    left: 12px;
    right: 12px;
    top: 76px !important;
    width: auto;
  }

  .profile-drawer {
    left: 12px;
    right: 12px;
    top: 78px;
    bottom: 12px;
    width: auto;
  }
}
</style>
