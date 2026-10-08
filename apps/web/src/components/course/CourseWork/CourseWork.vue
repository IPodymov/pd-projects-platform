<script setup lang="ts">
import { inject } from 'vue'
import { courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
const workspace = inject(courseWorkspaceKey)
if (!workspace) throw new Error('Course workspace is unavailable')
const { course, assignments, selected, text, op, own, latest, save } = workspace
</script>
<template>
  <section v-if="own" class="panel" data-layout="courseview-style-8">
    <h2>Моя работа · принято {{ own.progress }}%</h2>
    <p class="helper">
      Статус записи: {{ own.status }}. Прогресс учитывает пройденные уроки и принятые обязательные
      задания.
    </p>
    <form
      v-if="assignments.length && own.status === 'active' && course?.status === 'published'"
      class="form"
      @submit.prevent="save(true)"
    >
      <label
        >Задание<select v-model="selected" required>
          <option v-for="a in assignments" :key="a.id" :value="a.id">{{ a.title }}</option>
        </select></label
      ><label
        >Результат<textarea
          v-model="text"
          required
          :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
        />
      </label>
      <p v-if="latest?.status === 'revision'" class="helper">
        Замечания к предыдущей отправке: {{ latest.feedback }}
      </p>
      <div class="actions">
        <Button
          label="Сохранить черновик"
          severity="secondary"
          :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
          :loading="op.busy.value"
          @click="save()"
        /><Button
          type="submit"
          label="Отправить на проверку"
          :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
          :loading="op.busy.value"
        />
      </div>
    </form>
  </section>
</template>
<style src="./CourseWork.css" scoped></style>
