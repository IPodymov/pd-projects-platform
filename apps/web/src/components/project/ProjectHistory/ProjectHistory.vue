<script setup lang="ts">
import { computed, inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import { formatDateTime } from '@/utils/dateTime'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const { versions, docs, submissions } = workspace
const events = computed(() =>
  [
    ...versions.value
      .filter((v) => docs.value.some((d) => d.id === v.document))
      .map((v) => ({
        id: v.id,
        title: 'Загружен файл ' + v.filename,
        detail: Math.ceil(v.size / 1024) + ' КБ',
        date: v.created_at,
      })),
    ...submissions.value.map((s) => ({
      id: s.id,
      title: s.feedback ? 'Комментарий преподавателя' : 'Отправлена работа',
      detail: s.feedback || s.text.slice(0, 100),
      date: s.updated_at,
    })),
  ]
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 8),
)
</script>
<template>
  <section class="panel project-history">
    <h2>История изменений</h2>
    <p v-if="!events.length" class="helper">
      История появится после загрузки материалов и отправки работ.
    </p>
    <article v-for="event in events" :key="event.id">
      <strong>{{ event.title }}</strong>
      <p>{{ event.detail }}</p>
      <time :datetime="event.date">{{ formatDateTime(event.date) }}</time>
    </article>
  </section>
</template>
<style src="./ProjectHistory.css" scoped></style>
