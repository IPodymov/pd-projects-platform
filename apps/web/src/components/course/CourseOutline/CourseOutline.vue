<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import StatusBadge from '@/components/common/StatusBadge/StatusBadge.vue'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { lessons, assignments, own } = workspace
</script>
<template>
  <section class="panel course-outline">
    <h2>Структура курса</h2>
    <p v-if="!lessons.length && !assignments.length" class="helper">
      Добавьте первый урок или задание.
    </p>
    <a v-for="(lesson, index) in lessons" :key="lesson.id" :href="'#course-lesson-' + lesson.id"
      ><strong>{{ index + 1 }}. {{ lesson.title }}</strong
      ><StatusBadge :status="lesson.completed ? 'completed' : 'planned'"
    /></a>
    <div v-for="a in assignments" :key="a.id">
      <strong>{{ a.title }}</strong
      ><span class="helper">{{
        a.required ? 'Обязательное задание' : 'Дополнительное задание'
      }}</span>
    </div>
    <p v-if="own" class="helper">Прогресс: {{ own.progress }}%</p>
    <RouterLink to="/workshops">Мастер-классы и запись →</RouterLink>
  </section>
</template>
<style src="./CourseOutline.css" scoped></style>
