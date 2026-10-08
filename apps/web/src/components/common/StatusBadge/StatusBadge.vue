<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ status: string }>()
const labels: Record<string, string> = {
  draft: 'Черновик',
  active: 'В работе',
  submitted: 'На проверке',
  revision: 'На доработке',
  accepted: 'Утверждён',
  archived: 'В архиве',
  published: 'Опубликован',
  completed: 'Завершён',
  cancelled: 'Отменён',
  planned: 'Запланирован',
  scheduled: 'Запланировано',
  pending: 'Ожидает',
  done: 'Готово',
  unavailable: 'Без извлечения текста',
}
const label = computed(() => labels[props.status] || props.status)
const tone = computed(() =>
  ['accepted', 'completed', 'published', 'done'].includes(props.status)
    ? 'success'
    : ['submitted', 'revision', 'pending'].includes(props.status)
      ? 'warning'
      : ['active'].includes(props.status)
        ? 'primary'
        : 'neutral',
)
</script>
<template>
  <span class="status-badge" :class="'status-badge--' + tone">{{ label }}</span>
</template>
<style src="./StatusBadge.css" scoped></style>
