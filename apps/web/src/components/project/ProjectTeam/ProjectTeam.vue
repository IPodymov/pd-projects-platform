<script setup lang="ts">
import { inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
import { api } from '@/api'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const { session, p, members, chosenMember, busy, team, memberRole, id, run } = workspace
</script>
<template>
  <section class="panel">
    <h2>Команда</h2>
    <p v-for="m in team" :key="m.id">
      {{ m.name }} · {{ m.role === 'leader' ? 'Лидер' : 'Участник' }}
      <Button
        v-if="session.staff"
        :label="m.role === 'leader' ? 'Сделать участником' : 'Назначить лидером'"
        text
        :disabled="busy"
        @click="
          run(() =>
            api(
              'project-members/' + m.id + '/',
              'PATCH',
              { role: m.role === 'leader' ? 'member' : 'leader' },
              m.updated_at,
            ),
          )
        "
      />
    </p>
    <p class="helper">
      {{ p?.members.length }} участников. Назначение доступно преподавателю класса.
    </p>
    <form
      v-if="session.staff"
      class="form"
      @submit.prevent="
        run(() =>
          api('project-members/', 'POST', {
            project: id,
            user: chosenMember,
            role: memberRole,
          }),
        )
      "
    >
      <label
        >Участник<select v-model="chosenMember" required>
          <option v-for="m in members" :key="m.id" :value="m.user">
            {{ m.name }} · {{ m.email }}
          </option>
        </select></label
      ><label
        >Роль в команде<select v-model="memberRole">
          <option value="member">Участник</option>
          <option value="leader">Лидер</option>
        </select></label
      ><Button type="submit" label="Добавить в команду" :loading="busy" />
    </form>
  </section>
</template>
<style src="./ProjectTeam.css" scoped></style>
