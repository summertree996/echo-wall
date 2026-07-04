<script setup lang="ts">
import { MousePointer2, Move, StickyNote } from '@lucide/vue'

type Tool = 'add' | 'react' | 'drag'

const props = defineProps<{
  modelValue: Tool
  paused?: boolean
  disabledTools?: Tool[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: Tool]
}>()

function selectTool(tool: Tool) {
  if (isToolDisabled(tool)) return
  emit('update:modelValue', tool)
}

function isToolDisabled(tool: Tool) {
  return Boolean(props.paused || props.disabledTools?.includes(tool))
}
</script>

<template>
  <nav class="tool-dock" :class="{ paused }" aria-label="墙面操作模式" @pointerdown.stop @click.stop>
    <button :class="{ active: modelValue === 'add' }" :disabled="isToolDisabled('add')" @click="selectTool('add')">
      <StickyNote :size="20" /><span>贴一张</span>
    </button>
    <button :class="{ active: modelValue === 'react' }" :disabled="isToolDisabled('react')" @click="selectTool('react')">
      <MousePointer2 :size="20" /><span>浏览</span>
    </button>
    <button :class="{ active: modelValue === 'drag' }" :disabled="isToolDisabled('drag')" @click="selectTool('drag')">
      <Move :size="20" /><span>移动</span>
    </button>
  </nav>
</template>
