<script setup lang="ts">
import { computed } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import { Bold, Italic, List, ListOrdered, Strikethrough, Underline as UnderlineIcon } from '@lucide/vue'

const props = withDefaults(defineProps<{ initial?: Record<string, unknown> | null; submitLabel?: string }>(), {
  submitLabel: '发表',
})
const emit = defineEmits<{ submit: [payload: { json: Record<string, unknown>; text: string }] }>()

const editor = useEditor({
  extensions: [
    StarterKit.configure({
      blockquote: false,
      code: false,
      codeBlock: false,
      heading: false,
      horizontalRule: false,
    }),
    Underline,
  ],
  content: props.initial || { type: 'doc', content: [{ type: 'paragraph' }] },
  editorProps: {
    attributes: { class: 'editor-surface' },
  },
})

const textLength = computed(() => editor.value?.getText().length || 0)
const canSubmit = computed(() => textLength.value > 0 && textLength.value <= 150)

function submit() {
  if (!editor.value || !canSubmit.value) return
  emit('submit', { json: editor.value.getJSON() as Record<string, unknown>, text: editor.value.getText() })
}
</script>

<template>
  <div class="rich-editor">
    <div class="rt-toolbar">
      <button type="button" title="加粗" :class="{ on: editor?.isActive('bold') }" @click="editor?.chain().focus().toggleBold().run()"><Bold :size="16" /></button>
      <button type="button" title="斜体" :class="{ on: editor?.isActive('italic') }" @click="editor?.chain().focus().toggleItalic().run()"><Italic :size="16" /></button>
      <button type="button" title="下划线" :class="{ on: editor?.isActive('underline') }" @click="editor?.chain().focus().toggleUnderline().run()"><UnderlineIcon :size="16" /></button>
      <button type="button" title="删除线" :class="{ on: editor?.isActive('strike') }" @click="editor?.chain().focus().toggleStrike().run()"><Strikethrough :size="16" /></button>
      <button type="button" title="无序列表" :class="{ on: editor?.isActive('bulletList') }" @click="editor?.chain().focus().toggleBulletList().run()"><List :size="16" /></button>
      <button type="button" title="有序列表" :class="{ on: editor?.isActive('orderedList') }" @click="editor?.chain().focus().toggleOrderedList().run()"><ListOrdered :size="16" /></button>
    </div>
    <EditorContent :editor="editor" />
    <div class="editor-foot">
      <span :class="{ warn: textLength > 120, danger: textLength > 150 }">{{ textLength }}/150</span>
      <button class="primary" :disabled="!canSubmit" @click="submit">{{ submitLabel }}</button>
    </div>
  </div>
</template>
