<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowUpRight, Clock3, Link2, LogOut, Mail, StickyNote, User, Users } from '@lucide/vue'
import ProfileActivityList from '../components/ProfileActivityList.vue'
import { api } from '../services/api'
import { useAuthStore } from '../stores/auth'

interface ProfileUser {
  nickname: string
  email: string
  role: string
  joinedAt?: string
  avatarInitial?: string
}

interface ProfileActivityItem {
  id: string
  wallId: string
  wallTitle: string
  excerpt: string
  createdAt: string
  tone?: 'positive' | 'neutral' | 'question'
  toneLabel?: string
  replyCount?: number
}

interface ProfileSpace {
  id: string
  title: string
  teacherName?: string
  lastActiveAt: string
  roleInSpace?: string
  latestPrompt?: string
  contributionCount?: number
  status?: 'active' | 'quiet' | 'ended'
}

const props = withDefaults(
  defineProps<{
    profile?: ProfileUser
    recentActivities?: ProfileActivityItem[]
    recentSpaces?: ProfileSpace[]
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)

const auth = useAuthStore()
const router = useRouter()
const activityLoading = ref(false)
const activityItems = ref<ProfileActivityItem[]>([])
const spaceItems = ref<ProfileSpace[]>([])

const currentProfile = computed<ProfileUser>(() => props.profile ?? {
  nickname: auth.user?.nickname || '参与者',
  email: auth.user?.email || '',
  role: auth.user?.is_admin ? 'admin' : 'user',
  avatarInitial: auth.user?.nickname?.slice(0, 1) || 'E',
})
const isLoading = computed(() => props.loading || activityLoading.value)
const recentActivities = computed(() => props.recentActivities ?? activityItems.value)
const recentSpaces = computed(() => props.recentSpaces ?? spaceItems.value)
const avatarInitial = computed(() => {
  const seed = currentProfile.value.avatarInitial || currentProfile.value.nickname.trim()
  return seed.slice(0, 1).toUpperCase() || 'E'
})
const recentActivityCount = computed(() => recentActivities.value.length)
const recentSpaceCount = computed(() => recentSpaces.value.length)
const contributionCount = computed(() => recentSpaces.value.reduce((total, space) => total + (space.contributionCount ?? 0), 0))
const joinedLabel = computed(() => {
  const joinedAt = currentProfile.value.joinedAt
  if (!joinedAt) return '最近加入'
  const dateText = formatProfileDate(joinedAt)
  return dateText === joinedAt ? dateText : `加入于 ${dateText}`
})

function formatProfileDate(value: string | undefined) {
  if (!value) return '最近加入'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function formatSpaceTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function spaceStatusLabel(status: ProfileSpace['status']) {
  if (status === 'active') return '进行中'
  if (status === 'ended') return '已结束'
  return '最近参与'
}

function spaceStatusClass(status: ProfileSpace['status']) {
  if (status === 'active') return 'status-active'
  if (status === 'ended') return 'status-ended'
  return 'status-quiet'
}

async function loadActivity() {
  activityLoading.value = true
  try {
    const data = await api.meActivity()
    activityItems.value = data.recent_activities.map((item) => ({
      id: item.id,
      wallId: item.wall_id,
      wallTitle: item.wall_title,
      excerpt: item.excerpt,
      createdAt: item.created_at,
      tone: item.tone,
      toneLabel: item.tone_label,
      replyCount: item.reply_count,
    }))
    spaceItems.value = data.recent_spaces.map((space) => ({
      id: space.id,
      title: space.title,
      lastActiveAt: space.last_active_at,
      roleInSpace: space.role_in_space,
      latestPrompt: space.latest_prompt,
      contributionCount: space.contribution_count,
      status: space.status,
    }))
  } finally {
    activityLoading.value = false
  }
}

async function logout() {
  await auth.logout()
  await router.replace('/enter')
}

onMounted(async () => {
  const user = await auth.refreshSession()
  if (!user) {
    await router.replace('/enter')
    return
  }
  await loadActivity()
})
</script>

<template>
  <main class="profile-view">
    <section class="profile-hero" aria-labelledby="profile-title">
      <div class="profile-hero-main">
        <div class="profile-brand">
          <span class="profile-brand-mark">
            <StickyNote :size="18" aria-hidden="true" />
          </span>
          <span>ECHO</span>
        </div>
        <button class="profile-logout" type="button" @click="logout">
          <LogOut :size="16" aria-hidden="true" />
          退出
        </button>

        <div class="profile-identity">
          <div class="profile-avatar" aria-hidden="true">{{ avatarInitial }}</div>
          <div class="profile-title-block">
            <h1 id="profile-title">{{ currentProfile.nickname }}</h1>
            <p>最近的发言和参与，都收在一处。</p>
            <div class="profile-meta">
              <span v-if="currentProfile.email">
                <Mail :size="15" aria-hidden="true" />
                {{ currentProfile.email }}
              </span>
              <span>
                <User :size="15" aria-hidden="true" />
                {{ joinedLabel }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="profile-summary" aria-label="个人概览">
        <article>
          <strong>{{ recentActivityCount }}</strong>
          <span>便签</span>
        </article>
        <article>
          <strong>{{ recentSpaceCount }}</strong>
          <span>空间</span>
        </article>
        <article>
          <strong>{{ contributionCount }}</strong>
          <span>参与</span>
        </article>
      </div>
    </section>

    <section class="profile-content" aria-label="个人参与记录">
      <ProfileActivityList :items="recentActivities" :loading="isLoading" />

      <aside class="profile-side">
        <section class="spaces-panel" aria-labelledby="profile-spaces-title">
          <div class="spaces-head">
            <div>
              <span>空间</span>
              <h2 id="profile-spaces-title">最近参与</h2>
            </div>
            <Users :size="22" aria-hidden="true" />
          </div>

          <div v-if="isLoading" class="space-skeleton" aria-label="正在加载最近参与空间">
            <span v-for="index in 3" :key="index"></span>
          </div>

          <ul v-else-if="recentSpaces.length" class="space-list">
            <li v-for="space in recentSpaces" :key="space.id" class="space-item">
              <div class="space-row">
                <span :class="['space-status', spaceStatusClass(space.status)]">{{ spaceStatusLabel(space.status) }}</span>
                <span class="space-time">
                  <Clock3 :size="14" aria-hidden="true" />
                  {{ formatSpaceTime(space.lastActiveAt) }}
                </span>
              </div>
              <h3>{{ space.title }}</h3>
              <p v-if="space.latestPrompt">{{ space.latestPrompt }}</p>
              <footer>
                <span v-if="space.teacherName">{{ space.teacherName }}</span>
                <span>{{ space.roleInSpace || '参与者' }}</span>
                <span>{{ space.contributionCount ?? 0 }} 次参与</span>
              </footer>
              <RouterLink class="space-link" :to="{ name: 'wall', params: { wallId: space.id } }" :aria-label="`打开${space.title}`">
                继续参与
                <ArrowUpRight :size="15" aria-hidden="true" />
              </RouterLink>
            </li>
          </ul>

          <div v-else class="profile-empty">
            <Link2 :size="32" aria-hidden="true" />
            <h3>还没有参与空间</h3>
            <p>收到新的邀请后，再回来看看。</p>
          </div>
        </section>

        <section class="profile-note" aria-label="个人备忘">
          <span class="note-mark">E</span>
          <div>
            <h2>慢慢收好</h2>
            <p>把想法、回应和参与留在一处。</p>
          </div>
        </section>
      </aside>
    </section>
  </main>
</template>

<style scoped>
.profile-view {
  --profile-bg: #f4f2ef;
  --profile-bg-cool: #eef1f6;
  --profile-surface: rgba(255, 255, 255, 0.78);
  --profile-line: rgba(223, 226, 235, 0.82);
  --profile-shadow: 0 1px 2px rgba(28, 30, 45, 0.06), 0 18px 44px rgba(28, 30, 45, 0.08);

  position: relative;
  isolation: isolate;
  min-height: 100vh;
  overflow: hidden;
  padding: 40px 34px 48px;
  color: var(--ink, #23262e);
  background: linear-gradient(155deg, var(--profile-bg) 0%, #fafaf8 48%, var(--profile-bg-cool) 100%);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.profile-view::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  background-image: radial-gradient(circle, rgba(90, 96, 120, 0.24) 0.8px, transparent 0.8px);
  background-size: 26px 26px;
  opacity: 0.12;
  pointer-events: none;
}

.profile-hero,
.profile-content {
  width: min(1120px, 100%);
  margin: 0 auto;
}

.profile-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 360px);
  gap: 18px;
  align-items: stretch;
}

.profile-hero-main,
.profile-summary,
.spaces-panel,
.profile-note {
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 16px;
  background: var(--profile-surface);
  box-shadow: var(--profile-shadow);
  backdrop-filter: blur(18px);
}

.profile-hero-main {
  position: relative;
  min-width: 0;
  padding: 30px;
}

.profile-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ink-3, #8b909c);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
}

.profile-brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--brand, #14161c);
  box-shadow: 0 10px 24px rgba(20, 22, 28, 0.14);
}

.profile-logout {
  position: absolute;
  top: 26px;
  right: 26px;
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid rgba(224, 227, 235, 0.9);
  border-radius: 999px;
  padding: 0 13px;
  color: var(--ink-2, #545b68);
  background: rgba(255, 255, 255, 0.68);
  box-shadow: 0 8px 22px rgba(28, 30, 45, 0.07);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  transition: transform 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.profile-logout:hover {
  border-color: rgba(91, 91, 240, 0.32);
  color: var(--accent, #5b5bf0);
  transform: translateY(-1px);
}

.profile-identity {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  margin-top: 42px;
}

.profile-avatar {
  width: 96px;
  height: 96px;
  border-radius: 26px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: #fff;
  background:
    linear-gradient(145deg, #14161c 0%, #3f4268 54%, #5b5bf0 100%);
  box-shadow: 0 20px 42px rgba(43, 45, 82, 0.18);
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 0;
}

.profile-title-block {
  min-width: 0;
}

.spaces-head span {
  display: block;
  color: var(--accent, #5b5bf0);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.profile-title-block h1 {
  margin: 0;
  color: var(--ink, #23262e);
  font-size: clamp(38px, 5vw, 58px);
  font-weight: 800;
  line-height: 1.08;
  letter-spacing: 0;
}

.profile-title-block p {
  max-width: 460px;
  margin: 16px 0 18px;
  color: var(--ink-2, #545b68);
  font-size: 17px;
  line-height: 1.7;
}

.profile-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}

.profile-meta span {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid rgba(224, 227, 235, 0.88);
  border-radius: 999px;
  padding: 0 12px;
  color: var(--ink-2, #545b68);
  background: rgba(255, 255, 255, 0.58);
  font-size: 13px;
  font-weight: 700;
}

.profile-summary {
  display: grid;
  align-content: center;
  padding: 22px;
}

.profile-summary article {
  display: grid;
  gap: 4px;
  padding: 20px 0;
  border-bottom: 1px solid var(--profile-line);
}

.profile-summary article:last-child {
  border-bottom: none;
}

.profile-summary strong {
  color: var(--brand, #14161c);
  font-size: 38px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
}

.profile-summary span {
  color: var(--ink-3, #8b909c);
  font-size: 13px;
  font-weight: 700;
}

.profile-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  gap: 18px;
  align-items: start;
  margin-top: 18px;
}

.profile-side {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.spaces-panel {
  padding: 24px;
}

.spaces-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.spaces-head h2 {
  margin: 6px 0 0;
  color: var(--ink, #23262e);
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: 0;
}

.spaces-head svg {
  color: var(--accent, #5b5bf0);
}

.space-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.space-item {
  position: relative;
  border-top: 1px solid var(--profile-line);
  padding: 18px 0;
  background: transparent;
}

.space-item:first-child {
  border-top: none;
}

.space-row,
.space-time,
.space-item footer,
.space-link {
  display: flex;
  align-items: center;
}

.space-row {
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.space-status {
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 11px;
  font-weight: 800;
}

.status-active {
  color: #178650;
  background: #dff6e9;
}

.status-quiet {
  color: #475569;
  background: #edf0f5;
}

.status-ended {
  color: var(--ink-2, #545b68);
  background: #eef0f4;
}

.space-time {
  gap: 5px;
  color: var(--ink-3, #8b909c);
  font-size: 12px;
  font-weight: 700;
}

.space-item h3 {
  margin: 0;
  color: var(--ink, #23262e);
  font-size: 17px;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: 0;
}

.space-item p {
  margin: 8px 0 14px;
  color: var(--ink-2, #545b68);
  font-size: 13px;
  line-height: 1.65;
}

.space-item footer {
  flex-wrap: wrap;
  gap: 8px;
  padding-right: 92px;
  color: var(--ink-3, #8b909c);
  font-size: 12px;
  font-weight: 700;
}

.space-link {
  position: absolute;
  right: 14px;
  bottom: 14px;
  gap: 5px;
  color: var(--brand, #14161c);
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
  transition: color 0.2s ease, transform 0.2s ease;
}

.space-link:hover {
  color: var(--accent, #5b5bf0);
  transform: translateX(2px);
}

.space-skeleton {
  display: grid;
  gap: 12px;
}

.space-skeleton span {
  height: 136px;
  border-radius: 16px;
  background: linear-gradient(90deg, #f0f2f6, #ffffff, #f0f2f6);
  background-size: 220% 100%;
  animation: profile-pulse 1.4s ease-in-out infinite;
}

.profile-empty {
  min-height: 220px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 10px;
  border: 1px dashed #d8dce6;
  border-radius: 16px;
  padding: 28px;
  text-align: center;
  color: var(--ink-2, #545b68);
  background: rgba(255, 255, 255, 0.58);
}

.profile-empty svg {
  color: var(--accent, #5b5bf0);
}

.profile-empty h3 {
  margin: 0;
  color: var(--ink, #23262e);
  font-size: 18px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: 0;
}

.profile-empty p {
  max-width: 310px;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}

.profile-note {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
}

.note-mark {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #fff;
  background: var(--brand, #14161c);
  font-size: 16px;
  font-weight: 800;
}

.profile-note h2 {
  margin: 0 0 6px;
  color: var(--ink, #23262e);
  font-size: 15px;
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: 0;
}

.profile-note p {
  margin: 0;
  color: var(--ink-2, #545b68);
  font-size: 13px;
  line-height: 1.6;
}

@keyframes profile-pulse {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}

@media (max-width: 920px) {
  .profile-view {
    padding: 22px;
  }

  .profile-hero,
  .profile-content {
    grid-template-columns: 1fr;
  }

  .profile-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .profile-summary article {
    padding: 4px 14px;
    border-right: 1px solid var(--profile-line);
    border-bottom: none;
  }

  .profile-summary article:last-child {
    border-right: none;
  }
}

@media (max-width: 640px) {
  .profile-view {
    padding: 16px;
  }

  .profile-hero-main,
  .profile-summary,
  .spaces-panel {
    border-radius: 16px;
  }

  .profile-hero-main,
  .spaces-panel {
    padding: 18px;
  }

  .profile-logout {
    top: 16px;
    right: 16px;
  }

  .profile-identity {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
    margin-top: 26px;
  }

  .profile-avatar {
    width: 74px;
    height: 74px;
    border-radius: 22px;
    font-size: 28px;
  }

  .profile-title-block h1 {
    font-size: 36px;
  }

  .profile-title-block p {
    font-size: 15px;
  }

  .profile-meta span {
    max-width: 100%;
  }

  .profile-summary {
    grid-template-columns: 1fr;
  }

  .profile-summary article {
    padding: 14px 0;
    border-right: none;
    border-bottom: 1px solid var(--profile-line);
  }

  .spaces-head h2 {
    font-size: 21px;
  }

  .space-item footer {
    padding-right: 0;
  }

  .space-link {
    position: static;
    margin-top: 14px;
  }
}
</style>
