<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { api } from '@/api'
import { errorMessage } from '@/utils/errors'
import PageState from '@/components/common/PageState/PageState.vue'
import ClassManagement from '@/components/classes/ClassManagement/ClassManagement.vue'
import ClassInvitations from '@/components/classes/ClassInvitations/ClassInvitations.vue'
import ClassStudents from '@/components/classes/ClassStudents/ClassStudents.vue'
import type { components } from '@future/api-client'
const classes = ref<components['schemas']['Classroom'][]>([]),
  selected = ref(''),
  loading = ref(true),
  error = ref('')
const classroom = computed(() => classes.value.find((c) => c.id === selected.value))
async function load() {
  loading.value = true
  error.value = ''
  try {
    classes.value = await api('classrooms/')
    if (!selected.value) selected.value = classes.value[0]?.id || ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">{{ classroom?.institution_name || 'Образовательная работа' }}</p>
      <h1>{{ classroom ? 'Класс ' + classroom.name : 'Классы' }}</h1>
      <p class="subtitle">{{ classroom?.academic_year }} · Учащиеся, проекты и приглашения</p>
    </div>
    <select v-model="selected" aria-label="Выберите класс">
      <option v-for="c in classes" :key="c.id" :value="c.id">
        {{ c.institution_name }} · {{ c.name }}
      </option>
    </select>
  </div>
  <PageState :loading="loading" :error="error" :empty="!classes.length" @retry="load"
    ><div v-if="selected" class="class-workspace">
      <div>
        <ClassStudents :key="selected" :classroom="selected" /><ClassManagement
          :key="'management-' + selected"
          :classroom="selected"
        />
      </div>
      <aside>
        <ClassInvitations :key="'invitations-' + selected" :classroom="selected" />
      </aside></div
  ></PageState>
</template>
<style src="./ClassesView.css" scoped></style>
