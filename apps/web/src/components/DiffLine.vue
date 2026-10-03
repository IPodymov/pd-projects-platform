<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ text: string; ranges?: number[][] }>()
const parts = computed(() => {
  const chars = Array.from(props.text),
    result: { text: string; changed: boolean }[] = []
  let offset = 0
  for (const [from, to] of props.ranges || []) {
    const start = Math.max(offset, from || 0),
      end = Math.min(chars.length, to || 0)
    result.push(
      { text: chars.slice(offset, start).join(''), changed: false },
      { text: chars.slice(start, end).join(''), changed: true },
    )
    offset = end
  }
  result.push({ text: chars.slice(offset).join(''), changed: false })
  return result
})
</script>
<template>
  <span
    v-for="(part, index) in parts"
    :key="index"
    :style="part.changed ? { fontWeight: '700', background: 'rgba(70,120,60,.18)' } : {}"
    >{{ part.text }}</span
  >
</template>
