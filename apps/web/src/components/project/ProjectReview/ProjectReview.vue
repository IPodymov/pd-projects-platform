<script setup lang="ts">
import { inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const { session, busy, milestones, stageForm, feedback, projectActions, projectTransition, stageTransition, createStage } = workspace
</script>
<template>
  <section class="panel" data-layout="projectview-style-1">
    <h2>Решение преподавателя</h2>
    <div class="actions">
      <Button
        v-for="status in projectActions()"
        :key="status"
        :label="
          (
            {
              active: 'Начать работу',
              submitted: 'Отправить на проверку',
              revision: 'Вернуть на доработку',
              accepted: 'Утвердить',
              archived: 'В архив',
            } as Record<string, string>
          )[status] || status
        "
        :loading="busy"
        @click="projectTransition(status)"
      />
    </div>
    <label v-if="session.staff">Замечание к проекту<input v-model="feedback" /></label>
    <h2 data-layout="projectview-style-2">Этапы проекта</h2>
    <form v-if="session.staff" class="form" @submit.prevent="createStage">
      <label>Название этапа<input v-model="stageForm.title" required /></label
      ><label>Критерии<textarea v-model="stageForm.criteria" required /></label
      ><label>Срок<input v-model="stageForm.due_at" type="datetime-local" required /></label
      ><Button label="Добавить этап" type="submit" :loading="busy" />
    </form>
    <article v-for="m in milestones" :key="m.id" data-layout="projectview-style-3">
      <h3>{{ m.title }} · {{ m.status }}</h3>
      <p>{{ m.criteria }}</p>
      <div class="actions">
        <Button
          v-if="session.staff && m.status === 'planned'"
          label="Начать этап"
          :loading="busy"
          @click="stageTransition(m, 'active')"
        /><Button
          v-if="m.status === 'active' || m.status === 'revision'"
          label="Отправить этап"
          :loading="busy"
          @click="stageTransition(m, 'submitted')"
        /><Button
          v-if="session.staff && m.status === 'submitted'"
          label="Принять этап"
          :loading="busy"
          @click="stageTransition(m, 'accepted')"
        /><Button
          v-if="session.staff && m.status === 'submitted'"
          label="На доработку"
          :loading="busy"
          @click="stageTransition(m, 'revision')"
        />
      </div>
    </article>
  </section>
</template>
<style src="./ProjectReview.css" scoped></style>
