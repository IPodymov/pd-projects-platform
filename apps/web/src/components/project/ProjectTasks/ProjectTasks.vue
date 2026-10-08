<script setup lang="ts">
import { inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
import { api } from '@/api'
import { formatDateTime } from '@/utils/dateTime'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const { session, tasks, busy, milestones, taskTitle, taskDue, taskMilestone, criteria, id, run } = workspace
</script>
<template>
  <section class="panel">
    <h2>Этапы и задания</h2>
    <form
      v-if="session.staff"
      class="form"
      @submit.prevent="
        run(() =>
          api('tasks/', 'POST', {
            project: id,
            title: taskTitle,
            stage: 'Основной',
            criteria,
            ...(taskMilestone ? { milestone: taskMilestone } : {}),
            due_at: new Date(taskDue).toISOString(),
          }),
        )
      "
    >
      <label>Новое задание<input v-model="taskTitle" required /></label
      ><label>Критерии<input v-model="criteria" required /></label
      ><label
        >Этап<select v-model="taskMilestone">
          <option value="">Без этапа</option>
          <option v-for="m in milestones" :key="m.id" :value="m.id">{{ m.title }}</option>
        </select></label
      ><label>Срок<input v-model="taskDue" type="datetime-local" required /></label
      ><Button type="submit" label="Назначить задание" :loading="busy" />
    </form>
    <p v-if="!tasks.length" class="helper">Задания ещё не назначены.</p>
    <p v-for="t in tasks" :key="t.id">
      <strong>{{ t.title }}</strong
      ><br /><span class="helper">{{ t.stage }} · до {{ formatDateTime(t.due_at) }}</span>
    </p>
  </section>
</template>
<style src="./ProjectTasks.css" scoped></style>
