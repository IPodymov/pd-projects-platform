<script setup lang="ts">
import { inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
import { api } from '@/api'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const { session, tasks, submissions, busy, draft, previous, selectedTask, work, reviewFeedback, run, sendWork, editDraft, revise } = workspace
</script>
<template>
  <section class="panel" data-layout="projectview-style-4">
    <h2>Отправить результат</h2>
    <form class="form" @submit.prevent="sendWork">
      <label
        >Задание<select v-model="selectedTask" required>
          <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select></label
      ><label>Результат<textarea v-model="work" required /></label
      ><label><input v-model="draft" type="checkbox" />Сохранить как черновик</label>
      <p v-if="previous" class="helper">Повторная работа после {{ previous.slice(0, 8) }}.</p>
      <Button
        type="submit"
        :label="draft ? 'Сохранить черновик' : 'Отправить на проверку'"
        :loading="busy"
      />
    </form>
    <div v-for="s in submissions" :key="s.id" class="panel" data-layout="projectview-style-5">
      <span class="badge">{{ s.result }}</span>
      <p>{{ s.text }}</p>
      <Button
        v-if="s.result === 'draft' && s.author === session.user?.id"
        label="Редактировать черновик"
        text
        @click="editDraft(s)"
      />
      <p v-if="s.feedback" class="helper">Замечания: {{ s.feedback }}</p>
      <Button
        v-if="s.author === session.user?.id && s.result === 'revision'"
        label="Подготовить повторную отправку"
        text
        @click="revise(s)"
      />
      <Button
        v-if="s.author === session.user?.id && s.result === 'draft'"
        label="Отправить черновик"
        :loading="busy"
        @click="run(() => api('submissions/' + s.id + '/send/', 'POST'))"
      />
      <form
        v-if="session.staff && s.result === 'submitted'"
        class="form"
        @submit.prevent="
          run(() =>
            api('submissions/' + s.id + '/review/', 'POST', {
              result: 'accepted',
              feedback: reviewFeedback[s.id] || '',
            }),
          )
        "
      >
        <label>Замечание<input v-model="reviewFeedback[s.id]" /></label>
        <div class="actions">
          <Button type="submit" label="Принять" :loading="busy" /><Button
            label="На доработку"
            severity="secondary"
            :loading="busy"
            @click="
              run(() =>
                api('submissions/' + s.id + '/review/', 'POST', {
                  result: 'revision',
                  feedback: reviewFeedback[s.id] || '',
                }),
              )
            "
          />
        </div>
      </form>
    </div>
  </section>
</template>
<style src="./ProjectSubmissions.css" scoped></style>
