<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
const { op, selected, projectForm, newProject, studentClasses, availableProjects, classroomName, assign } = inject(usersManagementKey)!
</script>
<template>
  <div v-if="selected">
    <h3>Проекты пользователя</h3>
    <p v-if="!selected.projects.length">Пока нет проектов.</p>
    <p v-for="p in selected.projects" :key="p.id">
      <RouterLink :to="'/projects/' + p.id">{{ p.title }}</RouterLink> · {{ p.status }}
    </p>
    <template v-if="selected.is_active && studentClasses.length">
      <form
        class="form"
        @submit.prevent="assign('add_project', projectForm, 'Пользователь добавлен в проект')"
      >
        <label
          >Существующий проект<select v-model="projectForm.project" required>
            <option value="">Выберите…</option>
            <option v-for="p in availableProjects" :key="p.id" :value="p.id">
              {{ p.title }} · {{ classroomName(p.classroom) }}
            </option>
          </select></label
        >
        <label
          >Роль<select v-model="projectForm.role">
            <option value="member">Участник</option>
            <option value="leader">Лидер</option>
          </select></label
        >
        <Button type="submit" label="Добавить в проект" :loading="op.busy.value" />
      </form>
      <h3>Создать проект для пользователя</h3>
      <form
        class="form"
        @submit.prevent="
          assign('create_project', newProject, 'Проект создан, пользователь добавлен')
        "
      >
        <label>Название<input v-model="newProject.title" required maxlength="200" /></label>
        <label>Описание<textarea v-model="newProject.description" /></label>
        <label
          >Класс проекта<select v-model="newProject.classroom" required>
            <option value="">Выберите…</option>
            <option v-for="c in studentClasses" :key="c.id" :value="c.id">
              {{ classroomName(c.id) }}
            </option>
          </select></label
        >
        <Button type="submit" label="Создать проект" :loading="op.busy.value" />
      </form>
    </template>
    <p v-else-if="selected.is_active" class="helper">
      Назначьте класс, чтобы добавлять курсы и проекты.
    </p>
  </div>
</template>
<style src="./UserProjectAssignments.css" scoped></style>
