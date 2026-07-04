<script setup lang="ts">
import { Bot, Copy, Database, Download, ExternalLink, FileText, Microscope, Save, Settings, Users } from '@lucide/vue'
import type { AccessMode, Wall } from '../types'

defineProps<{
  wall: Wall
  password: string
  saving: boolean
  aiTestLoading: boolean
  aiTestResult?: { status: 'ok' | 'error'; text: string }
  copied: boolean
}>()

const emit = defineEmits<{
  open: [wall: Wall]
  openResearch: [wall: Wall]
  save: [wall: Wall]
  testAi: [wall: Wall]
  exportJson: [wall: Wall]
  exportCsv: [wall: Wall]
  exportActionsCsv: [wall: Wall]
  exportResearchCsv: [wall: Wall]
  researchSummary: [wall: Wall]
  copy: [wall: Wall]
  'update:password': [value: string]
}>()

function accessLabel(mode: AccessMode) {
  if (mode === 'link_only') return '链接可浏览'
  if (mode === 'password_required') return '口令访问'
  return '登录参与'
}
</script>

<template>
  <article class="wall-card" :class="{ archived: wall.is_archived }">
    <header class="wall-card-head">
      <span>{{ wall.is_archived ? '已归档 · ' : '' }}{{ accessLabel(wall.access_mode) }}</span>
      <b>{{ wall.card_count }} 条反馈</b>
    </header>

    <div class="wall-card-body">
      <h2>{{ wall.title }}</h2>
      <p>{{ wall.description || '尚未填写描述' }}</p>
    </div>

    <div class="wall-card-quick">
      <span>{{ wall.ai_enabled ? 'AI 已启用' : 'AI 已关闭' }}</span>
      <span>{{ wall.is_anonymous ? '匿名展示' : '显示署名' }}</span>
      <span>{{ wall.ai_model.replace('deepseek-', '').toUpperCase() }}</span>
    </div>

    <div class="wall-primary-actions">
      <button class="primary" type="button" :disabled="wall.is_archived" @click="emit('open', wall)">
        <ExternalLink :size="16" />进入墙面
      </button>
      <button class="secondary" type="button" @click="emit('copy', wall)">
        <Copy :size="16" />{{ copied ? '已复制' : '复制链接' }}
      </button>
      <button class="secondary research-entry-button" type="button" @click="emit('openResearch', wall)">
        <Microscope :size="16" />科研看板
      </button>
    </div>

    <details class="ai-settings" @click.stop>
      <summary><Settings :size="15" />墙与 AI 设置</summary>
      <div class="ai-settings-head">
        <b>访问与现场</b>
        <div class="settings-actions">
          <label class="switch-line"><input v-model="wall.is_anonymous" type="checkbox" />匿名展示</label>
          <label class="switch-line"><input v-model="wall.is_archived" type="checkbox" />归档</label>
        </div>
      </div>
      <div class="ai-grid access-grid">
        <select v-model="wall.access_mode">
          <option value="link_only">链接可浏览</option>
          <option value="login_required">登录参与</option>
          <option value="password_required">口令访问</option>
        </select>
        <input
          v-if="wall.access_mode === 'password_required'"
          :value="password"
          type="password"
          :placeholder="wall.has_password ? '留空沿用现口令' : '设置访问口令'"
          @input="emit('update:password', ($event.target as HTMLInputElement).value)"
        />
      </div>
      <div class="ai-settings-head compact">
        <b>AI 分析</b>
        <label class="switch-line"><input v-model="wall.ai_enabled" type="checkbox" />启用</label>
      </div>
      <div class="ai-grid">
        <select v-model="wall.ai_model">
          <option value="deepseek-v4-flash">V4 Flash</option>
          <option value="deepseek-v4-pro">V4 Pro</option>
        </select>
        <label class="switch-line"><input v-model="wall.ai_thinking_enabled" type="checkbox" />Thinking</label>
        <select v-model="wall.ai_reasoning_effort" :disabled="!wall.ai_thinking_enabled">
          <option value="high">High</option>
          <option value="max">Max</option>
        </select>
        <button class="secondary save-ai" type="button" @click="emit('save', wall)">
          <Save :size="15" />{{ saving ? '保存中' : '保存设置' }}
        </button>
        <button class="secondary save-ai" type="button" :disabled="aiTestLoading" @click="emit('testAi', wall)">
          <Bot :size="15" />{{ aiTestLoading ? '测试中' : '测试连接' }}
        </button>
        <p
          v-if="aiTestResult"
          class="ai-test-result"
          :class="{ error: aiTestResult.status === 'error' }"
        >
          {{ aiTestResult.text }}
        </p>
      </div>
    </details>

    <footer>
      <span>数据导出</span>
      <div class="wall-actions">
        <button class="icon ghost" title="导出 JSON" @click="emit('exportJson', wall)"><Download :size="17" /></button>
        <button class="icon ghost" title="导出卡片 CSV" @click="emit('exportCsv', wall)"><FileText :size="17" /></button>
        <button class="icon ghost" title="导出动作 CSV" @click="emit('exportActionsCsv', wall)"><FileText :size="17" /></button>
        <button class="icon ghost" title="导出研究 CSV" @click="emit('exportResearchCsv', wall)"><Database :size="17" /></button>
        <button class="icon ghost" title="查看用户研究摘要" @click="emit('researchSummary', wall)"><Users :size="17" /></button>
      </div>
    </footer>
  </article>
</template>
