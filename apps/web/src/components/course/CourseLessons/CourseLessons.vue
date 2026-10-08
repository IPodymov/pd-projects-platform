<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
import ArticleBody from '@/components/common/ArticleBody/ArticleBody.vue'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { course, lessons, op, own, completeLesson } = workspace
</script>
<template>
  <section v-if="lessons.length" class="panel" data-layout="courseview-style-4">
    <h2>Уроки</h2>
    <article
      :id="'course-lesson-' + lesson.id"
      v-for="lesson in lessons"
      :key="lesson.id"
      data-layout="courseview-style-5"
    >
      <h3>{{ lesson.title }}</h3>
      <ArticleBody :body="lesson.body" />
      <span v-if="lesson.completed" class="badge">Пройден</span>
      <Button
        v-else-if="own?.status === 'active' && course?.status === 'published'"
        label="Отметить пройденным"
        :loading="op.busy.value"
        @click="completeLesson(lesson)"
      />
    </article>
  </section>
</template>
<style src="./CourseLessons.css" scoped></style>
