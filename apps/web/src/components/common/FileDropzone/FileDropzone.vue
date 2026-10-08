<script setup lang="ts">
import { ref } from 'vue'
const props = withDefaults(
  defineProps<{ accept?: string; disabled?: boolean; filename?: string; label?: string }>(),
  {
    accept: '.txt,.md,.csv,.docx,.pptx,.pdf,.png,.jpg,.jpeg',
    label: 'Перетащите файл или выберите с компьютера',
  },
)
const emit = defineEmits<{ select: [file: File] }>()
const dragging = ref(false),
  input = ref<HTMLInputElement>()
function pick(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file && !props.disabled) emit('select', file)
  target.value = ''
}
function drop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files[0]
  if (file && !props.disabled) emit('select', file)
}
</script>
<template>
  <div
    class="file-dropzone"
    :class="{ dragging, disabled }"
    @dragover.prevent="dragging = !disabled"
    @dragleave.prevent="dragging = false"
    @drop.prevent="drop"
  >
    <input
      ref="input"
      type="file"
      :accept="accept"
      :disabled="disabled"
      :aria-label="label"
      @change="pick"
    /><button type="button" :disabled="disabled" @click="input?.click()">
      <i class="pi pi-cloud-upload" aria-hidden="true" /><strong>{{ filename || label }}</strong
      ><span>TXT, MD, CSV, DOCX, PPTX, PDF и изображения · до 20 МБ</span>
    </button>
  </div>
</template>
<style src="./FileDropzone.css" scoped></style>
