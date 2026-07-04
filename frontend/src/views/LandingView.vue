<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { loginPathFor } from '../utils/entryResolver'

type LandingTag = {
  label: string
  tone?: 'positive' | 'negative'
}

type LandingReaction = {
  icon: string
  base: number
  delta: number
  isActive: boolean
  isBumping: boolean
  isResetting: boolean
}

type LandingCard = {
  id: string
  content: string
  tags: LandingTag[]
  reactions: LandingReaction[]
  avatar: string
  avatarGradient: string
  author: string
  time: string
  colorClass: string
  depthClass: string
  positionClass: string
  style: Record<string, string>
}

const emit = defineEmits<{
  enter: []
}>()
const router = useRouter()

const cards = reactive<LandingCard[]>([
  {
    id: 'feedback-space',
    content: '点赞这次新上线的反馈空间，想法能马上被大家看到，讨论氛围比传统问卷自然很多。',
    tags: [
      { label: '正向', tone: 'positive' },
      { label: '#体验' },
      { label: '#实时' },
    ],
    reactions: [
      { icon: '♡', base: 24, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 3, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 7, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '赵',
    avatarGradient: 'linear-gradient(135deg, #f472b6, #e879f9)',
    author: '赵欣',
    time: '08:40',
    colorClass: 'card-pink',
    depthClass: 'card-near',
    positionClass: 'card-1',
    style: { top: '10%', left: '8%' },
  },
  {
    id: 'presence',
    content: '实时同步的存在感很强，两边屏幕一起变化时，能让参与者感觉确实在共同完成一件事。',
    tags: [
      { label: '正向', tone: 'positive' },
      { label: '#实时' },
      { label: '#参与感' },
    ],
    reactions: [
      { icon: '♡', base: 31, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 2, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 12, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '陈',
    avatarGradient: 'linear-gradient(135deg, #34d399, #2dd4bf)',
    author: '陈一然',
    time: '08:38',
    colorClass: 'card-green',
    depthClass: 'card-near',
    positionClass: 'card-3',
    style: { top: '40%', left: '18%' },
  },
  {
    id: 'placement-preview',
    content: '希望发布前能看到大概会贴在哪里，哪怕只是半透明轮廓，也比直接弹窗更有掌控感。',
    tags: [{ label: '观察' }, { label: '#放置' }, { label: '#预览' }],
    reactions: [
      { icon: '♡', base: 18, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 5, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 9, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '孙',
    avatarGradient: 'linear-gradient(135deg, #fbbf24, #f97316)',
    author: '孙浩然',
    time: '08:44',
    colorClass: 'card-blue',
    depthClass: 'card-near',
    positionClass: 'card-6',
    style: { top: '70%', left: '42%' },
  },
  {
    id: 'theme-islands',
    content: '主题岛屿这个视图很适合会后复盘，能快速看到哪些问题是共识，哪些只是个别意见。',
    tags: [
      { label: '正向', tone: 'positive' },
      { label: '#主题聚类' },
    ],
    reactions: [
      { icon: '♡', base: 42, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 4, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 15, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '崔',
    avatarGradient: 'linear-gradient(135deg, #a78bfa, #c084fc)',
    author: '崔晓琳',
    time: '08:35',
    colorClass: 'card-yellow',
    depthClass: 'card-mid',
    positionClass: 'card-2',
    style: { top: '6%', left: '58%', width: '256px' },
  },
  {
    id: 'attention-fairness',
    content: '如果热门内容太抢眼，容易把晚到同学的声音盖住，建议热门入口做克制一些。',
    tags: [
      { label: '关注', tone: 'negative' },
      { label: '#注意力' },
      { label: '#公平' },
    ],
    reactions: [
      { icon: '♡', base: 15, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 8, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 21, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '林',
    avatarGradient: 'linear-gradient(135deg, #fb923c, #f472b6)',
    author: '林琪',
    time: '08:46',
    colorClass: 'card-purple',
    depthClass: 'card-mid',
    positionClass: 'card-4',
    style: { top: '44%', left: '65%', width: '248px' },
  },
  {
    id: 'anonymous-mode',
    content: '匿名模式切换不够清楚，大家可能会担心身份暴露。建议主持人开场时先讲清楚。',
    tags: [
      { label: '关注', tone: 'negative' },
      { label: '#匿名' },
    ],
    reactions: [
      { icon: '♡', base: 9, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '↓', base: 11, delta: 0, isActive: false, isBumping: false, isResetting: false },
      { icon: '？', base: 6, delta: 0, isActive: false, isBumping: false, isResetting: false },
    ],
    avatar: '王',
    avatarGradient: 'linear-gradient(135deg, #60a5fa, #818cf8)',
    author: '王美丽',
    time: '08:41',
    colorClass: 'card-peach',
    depthClass: 'card-far',
    positionClass: 'card-5',
    style: { top: '74%', left: '8%', width: '240px' },
  },
])

const animatedReactions = computed(() =>
  cards.flatMap((card) => (card.depthClass === 'card-far' ? [] : card.reactions)),
)

let reactionTimer: number | undefined
let reactionCycleStartedAt = 0
let reactionCycleDuration = 0
const pendingTimers: number[] = []

function handleEnter() {
  emit('enter')
  router.push(loginPathFor())
}

function currentCount(reaction: LandingReaction) {
  return reaction.base + reaction.delta
}

function resetReactionCounts() {
  animatedReactions.value.forEach((reaction) => {
    reaction.delta = 0
    reaction.isActive = false
    reaction.isBumping = false
    reaction.isResetting = true

    pendingTimers.push(
      window.setTimeout(() => {
        reaction.isResetting = false
      }, 520),
    )
  })
}

function bumpReaction(reaction: LandingReaction) {
  const step = Math.random() > 0.72 ? 2 : 1

  reaction.delta = Math.min(reaction.delta + step, 8)
  reaction.isBumping = false

  window.requestAnimationFrame(() => {
    reaction.isActive = true
    reaction.isBumping = true
  })

  pendingTimers.push(
    window.setTimeout(() => {
      reaction.isActive = false
      reaction.isBumping = false
    }, 720),
  )
}

function scheduleReaction(delay: number) {
  reactionTimer = window.setTimeout(animateReaction, delay)
}

function animateReaction() {
  const reactions = animatedReactions.value

  if (!reactions.length) return

  if (Date.now() - reactionCycleStartedAt > reactionCycleDuration) {
    resetReactionCounts()
    reactionCycleStartedAt = Date.now()
    reactionCycleDuration = 19000 + Math.random() * 5000
    scheduleReaction(1800)
    return
  }

  const shuffled = [...reactions].sort(() => Math.random() - 0.5)
  const bumpTotal = Math.random() > 0.66 ? 3 : 2

  shuffled.slice(0, bumpTotal).forEach((reaction, index) => {
    pendingTimers.push(window.setTimeout(() => bumpReaction(reaction), index * 220))
  })

  scheduleReaction(2600 + Math.random() * 1400)
}

onMounted(() => {
  reactionCycleStartedAt = Date.now()
  reactionCycleDuration = 19000 + Math.random() * 5000
  scheduleReaction(2200)
})

onUnmounted(() => {
  if (reactionTimer !== undefined) {
    window.clearTimeout(reactionTimer)
  }

  pendingTimers.forEach((timer) => window.clearTimeout(timer))
})
</script>

<template>
  <main class="landing-page" aria-labelledby="landing-title">
    <div class="dot-grid" aria-hidden="true"></div>

    <section class="hero">
      <div class="hero-content">
        <div class="hero-label">Expression Canvas for Heard Opinions</div>
        <h1 id="landing-title" class="hero-title">ECHO</h1>
        <p class="hero-subtitle">让每一个声音，被听见。</p>
        <button class="hero-cta" type="button" @click="handleEnter">
          开始表达
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
            <path d="M3 8h10M9 4l4 4-4 4"></path>
          </svg>
        </button>
      </div>

      <div class="cards-canvas" aria-hidden="true">
        <article
          v-for="card in cards"
          :key="card.id"
          class="card"
          :class="[card.colorClass, card.depthClass, card.positionClass]"
          :style="card.style"
        >
          <p class="card-content">{{ card.content }}</p>

          <div class="card-tags">
            <span
              v-for="tag in card.tags"
              :key="`${card.id}-${tag.label}`"
              class="card-tag"
              :class="tag.tone"
            >
              {{ tag.label }}
            </span>
          </div>

          <div class="card-reactions">
            <span
              v-for="reaction in card.reactions"
              :key="`${card.id}-${reaction.icon}`"
              class="card-reaction"
              :class="{ 'is-active': reaction.isActive }"
            >
              <span class="icon">{{ reaction.icon }}</span>
              <span
                class="count"
                :class="{ 'is-bumping': reaction.isBumping, 'is-resetting': reaction.isResetting }"
              >
                {{ currentCount(reaction) }}
              </span>
            </span>
          </div>

          <footer class="card-footer">
            <div class="card-avatar" :style="{ background: card.avatarGradient }">
              {{ card.avatar }}
            </div>
            <span class="card-author">{{ card.author }}</span>
            <span class="card-time">{{ card.time }}</span>
          </footer>
        </article>
      </div>
    </section>

    <footer class="footer">
      <p class="footer-text">北京大学教育学院</p>
    </footer>
  </main>
</template>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700;800&family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap");

.landing-page {
  --landing-bg: #f4f2ef;
  --landing-bg-cool: #eef1f6;
  --landing-text-primary: #23262e;
  --landing-text-secondary: #545b68;
  --landing-text-tertiary: #8b909c;
  --landing-brand: #14161c;
  --landing-card-shadow: 0 1px 2px rgba(28, 30, 45, 0.08), 0 18px 42px rgba(28, 30, 45, 0.12);

  position: relative;
  isolation: isolate;
  width: 100%;
  min-height: 100vh;
  min-height: 100svh;
  overflow: hidden;
  background: linear-gradient(160deg, var(--landing-bg) 0%, #fafaf8 46%, var(--landing-bg-cool) 100%);
  color: var(--landing-text-primary);
  font-family: "Noto Sans SC", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.dot-grid {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-image: radial-gradient(circle, rgba(90, 96, 120, 0.26) 0.8px, transparent 0.8px);
  background-size: 26px 26px;
  opacity: 0.16;
  pointer-events: none;
}

.hero {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  min-height: 100svh;
  display: flex;
  align-items: center;
  padding: 0 52px 54px;
}

.hero-content {
  position: relative;
  z-index: 10;
  max-width: 520px;
  margin-left: 7%;
  transform: translateY(-1.5vh);
}

.hero-label {
  margin-bottom: 22px;
  color: var(--landing-text-tertiary);
  font-family: "Inter", sans-serif;
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0;
  line-height: 1.4;
  text-transform: uppercase;
  opacity: 0;
  animation: landingFadeInUp 0.8s ease 0.2s forwards;
}

.hero-title {
  margin: 0 0 30px;
  color: var(--landing-text-primary);
  font-family: "Inter", sans-serif;
  font-size: 82px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1;
  opacity: 0;
  animation: landingFadeInUp 0.8s ease 0.4s forwards;
}

.hero-subtitle {
  margin: 0 0 40px;
  color: var(--landing-text-secondary);
  font-family: "Noto Sans SC", sans-serif;
  font-size: 22px;
  font-weight: 400;
  line-height: 1.55;
  opacity: 0;
  animation: landingFadeInUp 0.8s ease 0.6s forwards;
}

.hero-cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: auto;
  border: none;
  border-radius: 999px;
  padding: 14px 32px;
  background: var(--landing-brand);
  box-shadow: 0 10px 28px rgba(20, 22, 28, 0.16);
  color: #fff;
  font-family: "Noto Sans SC", sans-serif;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
  cursor: pointer;
  opacity: 0;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    filter 0.2s ease;
  animation: landingFadeInUp 0.8s ease 0.8s forwards;
}

.hero-cta:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
  box-shadow: 0 14px 34px rgba(20, 22, 28, 0.2);
}

.hero-cta:focus-visible {
  outline: 3px solid rgba(91, 91, 240, 0.28);
  outline-offset: 4px;
}

.hero-cta svg {
  width: 15px;
  height: 15px;
  transition: transform 0.2s ease;
}

.hero-cta:hover svg {
  transform: translateX(3px);
}

.cards-canvas {
  position: absolute;
  top: 0;
  right: 0;
  width: 58%;
  height: 100vh;
  height: 100svh;
  overflow: hidden;
  pointer-events: none;
}

.cards-canvas::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  z-index: 5;
  width: 25%;
  height: 100%;
  background: linear-gradient(to right, var(--landing-bg) 0%, transparent 100%);
}

.cards-canvas::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  z-index: 5;
  width: 100%;
  height: 15%;
  background: linear-gradient(to top, var(--landing-bg) 0%, transparent 100%);
}

.card {
  position: absolute;
  width: 280px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 16px;
  padding: 20px 22px;
  box-shadow: var(--landing-card-shadow);
  animation-fill-mode: both;
}

.card::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(155deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0) 46%);
  pointer-events: none;
}

.card-content {
  position: relative;
  z-index: 1;
  margin: 0 0 14px;
  color: #2c3038;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.72;
}

.card-tags {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.card-tag {
  border-radius: 20px;
  padding: 3px 10px;
  background: rgba(255, 255, 255, 0.5);
  color: var(--landing-text-secondary);
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
}

.card-tag.positive {
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
}

.card-tag.negative {
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

.card-reactions {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
}

.card-reaction {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--landing-text-secondary);
  font-size: 12px;
  transition: color 0.28s ease;
}

.card-reaction .icon {
  font-size: 14px;
  line-height: 1;
  transition:
    color 0.28s ease,
    transform 0.28s ease;
}

.card-reaction .count {
  display: inline-block;
  min-width: 10px;
  color: var(--landing-text-primary);
  font-size: 13.5px;
  font-weight: 600;
  transition: color 0.28s ease;
}

.card-reaction.is-active {
  color: var(--landing-text-primary);
}

.card-reaction.is-active .icon {
  color: #ff5a79;
  transform: translateY(-1px);
}

.card-reaction .count.is-bumping {
  color: #ff5a79;
  animation: landingCountPulse 0.68s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.card-reaction .count.is-resetting {
  color: var(--landing-text-tertiary);
  animation: landingCountReset 0.5s ease;
}

.card-footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.card-author {
  color: var(--landing-text-primary);
  font-size: 12px;
  font-weight: 500;
}

.card-time {
  margin-left: auto;
  color: var(--landing-text-tertiary);
  font-size: 11px;
}

.card-pink {
  background: linear-gradient(160deg, #fef0f4, #fbdde6);
}

.card-green {
  background: linear-gradient(160deg, #ebf9ef, #d9f2e0);
}

.card-blue {
  background: linear-gradient(160deg, #ecf4fe, #d8e9fc);
}

.card-yellow {
  background: linear-gradient(160deg, #fdf8e2, #fbf0c6);
}

.card-purple {
  background: linear-gradient(160deg, #f4efff, #eae3fb);
}

.card-peach {
  background: linear-gradient(160deg, #fff7ed, #f1e7d7);
}

.card-near {
  z-index: 3;
  opacity: 1;
}

.card-mid {
  z-index: 2;
  transform-origin: center;
  opacity: 0.66;
}

.card-far {
  z-index: 1;
  opacity: 0.3;
  filter: blur(2px);
}

.card-1 {
  animation: landingBreathe1 7s ease-in-out 0.3s infinite both;
}

.card-2 {
  animation: landingBreathe2 8s ease-in-out 0.5s infinite both;
}

.card-3 {
  animation: landingBreathe3 6.5s ease-in-out 0.7s infinite both;
}

.card-4 {
  animation: landingBreathe4 9s ease-in-out 0.9s infinite both;
}

.card-5 {
  animation: landingBreathe5 7.5s ease-in-out 1.1s infinite both;
}

.card-6 {
  animation: landingBreathe6 8.5s ease-in-out 1.3s infinite both;
}

.footer {
  position: absolute;
  right: 52px;
  bottom: 28px;
  z-index: 20;
  padding: 0;
  text-align: right;
  pointer-events: none;
}

.footer-text {
  margin: 0;
  color: rgba(139, 144, 156, 0.72);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
}

@keyframes landingFadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes landingCountPulse {
  0% {
    transform: translateY(0) scale(1);
  }

  34% {
    transform: translateY(-4px) scale(1.46);
  }

  100% {
    transform: translateY(0) scale(1);
  }
}

@keyframes landingCountReset {
  0% {
    opacity: 0.45;
    transform: translateY(1px);
  }

  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes landingBreathe1 {
  0%,
  100% {
    opacity: 0.65;
    transform: rotate(-1.2deg) scale(0.92) translate(0, 0);
  }

  40% {
    opacity: 0.72;
    transform: rotate(-1.2deg) scale(0.92) translate(2px, -6px);
  }

  70% {
    opacity: 0.68;
    transform: rotate(-1.2deg) scale(0.92) translate(-1px, -3px);
  }
}

@keyframes landingBreathe2 {
  0%,
  100% {
    transform: rotate(1.8deg) translate(0, 0);
  }

  35% {
    transform: rotate(1.8deg) translate(-3px, -7px);
  }

  65% {
    transform: rotate(2.2deg) translate(1px, -4px);
  }
}

@keyframes landingBreathe3 {
  0%,
  100% {
    transform: rotate(-0.8deg) translate(0, 0);
  }

  45% {
    transform: rotate(-0.8deg) translate(2px, -8px);
  }

  75% {
    transform: rotate(-0.4deg) translate(-1px, -3px);
  }
}

@keyframes landingBreathe4 {
  0%,
  100% {
    opacity: 0.35;
    transform: rotate(2.2deg) scale(0.88) translate(0, 0);
  }

  50% {
    opacity: 0.4;
    transform: rotate(2.2deg) scale(0.88) translate(-2px, -5px);
  }
}

@keyframes landingBreathe5 {
  0%,
  100% {
    opacity: 0.35;
    transform: rotate(-2deg) scale(0.85) translate(0, 0);
  }

  55% {
    opacity: 0.4;
    transform: rotate(-2deg) scale(0.85) translate(3px, -4px);
  }
}

@keyframes landingBreathe6 {
  0%,
  100% {
    transform: rotate(1deg) translate(0, 0);
  }

  30% {
    transform: rotate(1deg) translate(-2px, -9px);
  }

  60% {
    transform: rotate(1.5deg) translate(1px, -5px);
  }
}

@media (max-width: 900px) {
  .hero {
    align-items: flex-start;
    padding: 104px 28px 76px;
  }

  .hero-content {
    max-width: 460px;
    margin-left: 0;
    transform: none;
  }

  .hero-title {
    font-size: 62px;
  }

  .hero-subtitle {
    font-size: 18px;
    line-height: 1.65;
  }

  .cards-canvas {
    right: -42%;
    width: 100%;
    opacity: 0.48;
  }

  .footer {
    right: 28px;
    bottom: 20px;
  }
}

@media (max-width: 640px) {
  .hero {
    padding: 86px 22px 72px;
  }

  .hero-label {
    max-width: 260px;
    margin-bottom: 18px;
    font-size: 9.5px;
    letter-spacing: 0;
  }

  .hero-title {
    margin-bottom: 24px;
    font-size: 54px;
  }

  .hero-subtitle {
    margin-bottom: 34px;
    font-size: 17px;
  }

  .hero-cta {
    padding: 13px 28px;
  }

  .cards-canvas {
    right: -86%;
    width: 158%;
    opacity: 0.34;
  }

  .card {
    width: 248px;
    padding: 18px 20px;
  }

  .footer {
    right: 22px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .hero-label,
  .hero-title,
  .hero-subtitle,
  .hero-cta,
  .card,
  .card-reaction .count.is-bumping,
  .card-reaction .count.is-resetting {
    animation: none;
  }

  .hero-label,
  .hero-title,
  .hero-subtitle,
  .hero-cta {
    opacity: 1;
  }

  .hero-cta,
  .hero-cta svg,
  .card-reaction,
  .card-reaction .icon,
  .card-reaction .count {
    transition: none;
  }
}
</style>
