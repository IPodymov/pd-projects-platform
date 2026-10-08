<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
const { op, selected, courseForm, studentClasses, availableCourses, courseClasses, classroomName, assign } = inject(usersManagementKey)!
</script>
<template>
  <div v-if="selected">
    <h3>Курсы пользователя</h3>
    <p v-if="!selected.enrollments.length">Пока нет записей на курсы.</p>
    <p v-for="e in selected.enrollments" :key="e.id">
      <RouterLink :to="'/courses/' + e.course">{{ e.course_title }}</RouterLink> · {{ e.status }} ·
      {{ e.progress }}%
    </p>
    <form
      v-if="selected.is_active && studentClasses.length"
      class="form"
      @submit.prevent="assign('add_course', courseForm, 'Пользователь записан на курс')"
    >
      <label
        >Опубликованный курс<select
          v-model="courseForm.course"
          required
          @change="courseForm.classroom = ''"
        >
          <option value="">Выберите…</option>
          <option v-for="c in availableCourses" :key="c.id" :value="c.id">{{ c.title }}</option>
        </select></label
      >
      <label
        >Класс<select v-model="courseForm.classroom" required>
          <option value="">Выберите…</option>
          <option v-for="c in courseClasses" :key="c.id" :value="c.id">
            {{ classroomName(c.id) }}
          </option>
        </select></label
      >
      <Button type="submit" label="Добавить в курс" :loading="op.busy.value" />
    </form>
  </div>
</template>
<style src="./UserCourseAssignments.css" scoped></style>
