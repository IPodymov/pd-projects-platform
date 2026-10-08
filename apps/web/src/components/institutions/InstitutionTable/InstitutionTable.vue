<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from 'primevue/button'
import type { components } from '@future/api-client'
const props = defineProps<{
  institutions: components['schemas']['Institution'][]
  classes: components['schemas']['Classroom'][]
  staff: components['schemas']['Staff'][]
  members: components['schemas']['Membership'][]
}>()
const search = ref('')
const visible = computed(() =>
  props.institutions.filter((i) => i.name.toLowerCase().includes(search.value.toLowerCase())),
)
function students(id: string) {
  const classes = new Set(props.classes.filter((c) => c.institution === id).map((c) => c.id))
  return new Set(
    props.members.filter((m) => !m.ended_at && classes.has(m.classroom)).map((m) => m.user),
  ).size
}
</script>
<template>
  <section class="panel">
    <div class="table-heading">
      <h2>Учреждения</h2>
      <input
        v-model="search"
        type="search"
        aria-label="Поиск учреждений"
        placeholder="Поиск по названию"
      />
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Классы</th>
            <th>Учащиеся</th>
            <th>Преподаватели</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="institution in visible" :key="institution.id">
            <td>
              <strong>{{ institution.name }}</strong
              ><span class="helper kind">{{
                { school: 'Школа', college: 'Колледж', university: 'Вуз' }[institution.kind]
              }}</span>
            </td>
            <td>{{ classes.filter((c) => c.institution === institution.id).length }}</td>
            <td>{{ students(institution.id) }}</td>
            <td>
              {{
                staff.filter(
                  (s) => s.active && s.institution === institution.id && s.role === 'teacher',
                ).length
              }}
            </td>
            <td>
              <RouterLink to="/classes"><Button text label="Классы" /></RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="!visible.length" class="helper">Учреждения не найдены.</p>
  </section>
</template>
<style src="./InstitutionTable.css" scoped></style>
