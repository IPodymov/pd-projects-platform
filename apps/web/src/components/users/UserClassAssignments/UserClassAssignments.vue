<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
const { op, selected, classForm, activeMemberships, transferClasses, classroomName, assign } = inject(usersManagementKey)!
</script>
<template>
  <div v-if="selected">
    <h3>Классы и история</h3>
    <p v-for="m in selected.memberships" :key="m.id">
      {{ classroomName(m.classroom) }} ·
      {{ m.ended_at ? 'Завершено ' + m.ended_at : 'Учится с ' + m.started_at }}
    </p>
    <form
      v-if="selected.is_active"
      class="form"
      @submit.prevent="
        assign(
          'set_class',
          {
            classroom: classForm.classroom,
            ...(classForm.membership ? { membership: classForm.membership } : {}),
          },
          'Класс изменён',
        )
      "
    >
      <label v-if="activeMemberships.length"
        >Текущий класс<select
          v-model="classForm.membership"
          required
          @change="classForm.classroom = ''"
        >
          <option v-for="m in activeMemberships" :key="m.id" :value="m.id">
            {{ classroomName(m.classroom) }}
          </option>
        </select></label
      >
      <label
        >Новый класс<select v-model="classForm.classroom" required>
          <option value="">Выберите…</option>
          <option v-for="c in transferClasses" :key="c.id" :value="c.id">
            {{ c.institution_name }} · {{ c.name }} · {{ c.academic_year }}
          </option>
        </select></label
      >
      <p class="helper">
        При переводе активные курсы перейдут в новый класс. История и участие в проектах сохранятся.
      </p>
      <Button
        type="submit"
        :label="activeMemberships.length ? 'Перевести в класс' : 'Назначить класс'"
        :loading="op.busy.value"
      />
    </form>
  </div>
</template>
<style src="./UserClassAssignments.css" scoped></style>
