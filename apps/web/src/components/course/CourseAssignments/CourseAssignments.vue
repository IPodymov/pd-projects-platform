<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import { formatDateTime } from '@/utils/dateTime'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { assignments } = workspace
</script>
<template>
  <section class="panel" data-layout="courseview-style-6">
    <h2>Задания</h2>
    <p v-if="!assignments.length" class="helper">Задания ещё не добавлены.</p>
    <article v-for="a in assignments" :key="a.id" data-layout="courseview-style-7">
      <h3>{{ a.title }}</h3>
      <p>{{ a.instructions }}</p>
      <p class="helper">Критерии: {{ a.criteria }}</p>
      <p class="helper">До {{ formatDateTime(a.due_at) }}</p>
    </article>
  </section>
</template>
<style src="./CourseAssignments.css" scoped></style>
