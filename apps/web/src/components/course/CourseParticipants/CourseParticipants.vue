<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { session, course, enrollments, members, participant, op, enroll, cancel } = workspace
</script>
<template>
  <section class="panel" data-layout="courseview-style-3" v-if="session.staff">
    <h2>Участники курса</h2>
    <form v-if="course?.status === 'published'" class="form" @submit.prevent="enroll">
      <label
        >Участник<select v-model="participant" required>
          <option value="">Выберите…</option>
          <option v-for="m in members" :key="m.id" :value="m.id">
            {{ m.name }} · {{ m.email }}
          </option>
        </select></label
      ><Button type="submit" label="Записать" :loading="op.busy.value" />
    </form>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Участник</th>
            <th>Статус</th>
            <th>Принято</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in enrollments" :key="e.id">
            <td>{{ e.user_name }}</td>
            <td>{{ e.status }}</td>
            <td>{{ e.progress }}%</td>
            <td>
              <Button
                v-if="e.status === 'active'"
                text
                label="Отменить запись"
                :disabled="op.busy.value"
                @click="cancel(e)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
<style src="./CourseParticipants.css" scoped></style>
