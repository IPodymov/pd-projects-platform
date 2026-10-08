<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { session, course, lessonForm, op, form, createLesson, createAssignment } = workspace
</script>
<template>
  <section
    v-if="session.managesCourses && course?.status === 'draft'"
    class="panel"
    data-layout="courseview-style-1"
  >
    <h2>Добавить урок</h2>
    <form class="form" @submit.prevent="createLesson">
      <label>Название<input v-model="lessonForm.title" required maxlength="200" /></label>
      <label>Содержание (Markdown)<textarea v-model="lessonForm.body" required /></label>
      <Button type="submit" label="Добавить урок" :loading="op.busy.value" />
    </form>
  </section>
  <section
    class="panel"
    data-layout="courseview-style-2"
    v-if="session.managesCourses && course?.status === 'draft'"
  >
    <h2>Добавить задание</h2>
    <form class="form" @submit.prevent="createAssignment">
      <label>Название<input v-model="form.title" required /></label
      ><label>Инструкция<textarea v-model="form.instructions" required /></label
      ><label>Критерии принятия<textarea v-model="form.criteria" required /></label
      ><label>Срок<input v-model="form.due_at" type="datetime-local" required /></label
      ><Button type="submit" label="Добавить" :loading="op.busy.value" />
    </form>
  </section>
</template>
<style src="./CourseBuilder.css" scoped></style>
