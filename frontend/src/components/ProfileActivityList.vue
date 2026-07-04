<script setup lang="ts">
import { Clock3, Heart, MessageCircle } from '@lucide/vue'

interface ActivityItem {
  id: string
  wallId: string
  wallTitle: string
  excerpt: string
  createdAt: string
  tone?: 'positive' | 'neutral' | 'question'
  toneLabel?: string
  replyCount?: number
}

const props = withDefaults(
  defineProps<{
    items: ActivityItem[]
    loading?: boolean
    emptyTitle?: string
    emptyText?: string
  }>(),
  {
    loading: false,
    emptyTitle: '还没有发言',
    emptyText: '第一张便签，等你写下。',
  },
)

function toneClass(tone: ActivityItem['tone']) {
  if (tone === 'positive') return 'tone-positive'
  if (tone === 'question') return 'tone-question'
  return 'tone-neutral'
}

function formatActivityTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}
</script>

<template>
  <section class="profile-activity-list" aria-labelledby="profile-activity-title">
    <div class="activity-list-head">
      <div>
        <span>最近发言</span>
        <h2 id="profile-activity-title">回声记录</h2>
      </div>
      <MessageCircle :size="22" aria-hidden="true" />
    </div>

    <div v-if="props.loading" class="activity-skeleton" aria-label="正在加载最近发言">
      <span v-for="index in 3" :key="index"></span>
    </div>

    <ul v-else-if="props.items.length" class="activity-items">
      <li v-for="item in props.items" :key="item.id" :class="['activity-item', toneClass(item.tone)]">
        <div class="activity-meta">
          <span class="tone-dot" aria-hidden="true"></span>
          <strong>{{ item.toneLabel || '便签' }}</strong>
          <span class="activity-time">
            <Clock3 :size="14" aria-hidden="true" />
            {{ formatActivityTime(item.createdAt) }}
          </span>
        </div>
        <p>{{ item.excerpt }}</p>
        <footer>
          <span>{{ item.wallTitle }}</span>
          <span v-if="item.replyCount !== undefined" class="reply-count">
            <Heart :size="14" aria-hidden="true" />
            {{ item.replyCount }} 次回应
          </span>
        </footer>
      </li>
    </ul>

    <div v-else class="profile-empty">
      <MessageCircle :size="32" aria-hidden="true" />
      <h3>{{ props.emptyTitle }}</h3>
      <p>{{ props.emptyText }}</p>
    </div>
  </section>
</template>

<style scoped>
.profile-activity-list {
  --activity-line: rgba(223, 226, 235, 0.82);
  --activity-shadow: 0 1px 2px rgba(28, 30, 45, 0.06), 0 18px 44px rgba(28, 30, 45, 0.08);

  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 16px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: var(--activity-shadow);
  backdrop-filter: blur(18px);
}

.activity-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.activity-list-head span {
  display: block;
  margin-bottom: 6px;
  color: var(--accent, #5b5bf0);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.activity-list-head h2 {
  margin: 0;
  color: var(--ink, #23262e);
  font-size: 24px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: 0;
}

.activity-list-head svg {
  flex: 0 0 auto;
  color: var(--accent, #5b5bf0);
}

.activity-items {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.activity-item {
  position: relative;
  border-top: 1px solid var(--activity-line);
  padding: 18px 0 18px 18px;
  background: transparent;
}

.activity-item:first-child {
  border-top: none;
}

.activity-item::before {
  content: "";
  position: absolute;
  left: 0;
  top: 25px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neu, #aab0ba);
}

.activity-item.tone-positive::before {
  background: var(--pos, #34c47f);
}

.activity-item.tone-question::before {
  background: var(--accent, #5b5bf0);
}

.activity-meta,
.activity-item footer,
.reply-count {
  display: flex;
  align-items: center;
}

.activity-meta {
  flex-wrap: wrap;
  gap: 8px;
  color: var(--ink-3, #8b909c);
  font-size: 12px;
  font-weight: 700;
}

.activity-meta strong {
  color: var(--ink, #23262e);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0;
}

.tone-dot {
  display: none;
}

.tone-positive .tone-dot {
  background: var(--pos, #34c47f);
}

.tone-question .tone-dot {
  background: var(--accent, #5b5bf0);
}

.activity-time {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.activity-item p {
  margin: 12px 0 14px;
  color: var(--ink, #23262e);
  font-size: 15px;
  line-height: 1.7;
}

.activity-item footer {
  justify-content: space-between;
  gap: 12px;
  color: var(--ink-3, #8b909c);
  font-size: 12px;
  font-weight: 700;
}

.reply-count {
  gap: 5px;
  white-space: nowrap;
}

.activity-skeleton {
  display: grid;
  gap: 12px;
}

.activity-skeleton span {
  height: 104px;
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

@keyframes profile-pulse {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}

@media (max-width: 640px) {
  .profile-activity-list {
    padding: 18px;
    border-radius: 16px;
  }

  .activity-list-head h2 {
    font-size: 21px;
  }

  .activity-item footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
