<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { session, course, ownClass, myMemberships, availableClasses, op, own, joinCourse } = workspace
</script>
<template>
  <section
    v-if="
      course?.status === 'published' &&
      (!own || own.status === 'cancelled') &&
      (myMemberships.length || session.managesCourses)
    "
    class="panel"
  >
    <h2>Запись на курс</h2>
    <form class="form" @submit.prevent="joinCourse">
      <label
        >Мой класс<select v-model="ownClass" required>
          <option
            v-for="c in availableClasses.filter(
              (c) =>
                c.institution === course?.institution &&
                (session.managesCourses || myMemberships.some((m) => m.classroom === c.id)),
            )"
            :key="c.id"
            :value="c.id"
          >
            {{ c.name }}
          </option>
        </select></label
      ><Button type="submit" label="Записаться" :loading="op.busy.value" />
    </form>
  </section>
</template>
<style src="./CourseJoin.css" scoped></style>
