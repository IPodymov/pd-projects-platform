<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
import { formatDateTime } from '@/utils/dateTime'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { session, works, feedback, op, review } = workspace
</script>
<template>
  <section class="panel" data-layout="courseview-style-9">
    <h2>История отправок</h2>
    <p v-if="!works.length" class="helper">Работы ещё не отправлены.</p>
    <article v-for="w in works" :key="w.id" data-layout="courseview-style-10">
      <span class="badge">{{ w.status }}</span>
      <p>{{ w.text }}</p>
      <p v-if="w.feedback" class="helper">Замечание: {{ w.feedback }}</p>
      <p class="helper">{{ formatDateTime(w.created_at) }} · отправка {{ w.id.slice(0, 8) }}</p>
      <form
        v-if="session.staff && w.status === 'submitted'"
        class="form"
        @submit.prevent="review(w, 'accepted')"
      >
        <label>Замечание<input v-model="feedback[w.id]" /></label>
        <div class="actions">
          <Button type="submit" label="Принять" :loading="op.busy.value" /><Button
            label="На доработку"
            severity="secondary"
            :loading="op.busy.value"
            @click="review(w, 'revision')"
          />
        </div>
      </form>
    </article>
  </section>
</template>
<style src="./CourseWorkHistory.css" scoped></style>
