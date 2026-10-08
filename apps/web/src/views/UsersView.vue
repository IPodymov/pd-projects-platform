<script setup lang="ts">
import { provide } from 'vue'
import { useUsersManagement, usersManagementKey } from '@/composables/useUsersManagement'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import { formatDateTime } from '@/utils/dateTime'
import UserStudentAssignment from '@/components/users/UserStudentAssignment/UserStudentAssignment.vue'
import UserDirectory from '@/components/users/UserDirectory/UserDirectory.vue'
import UserProfile from '@/components/users/UserProfile/UserProfile.vue'
import UserClassAssignments from '@/components/users/UserClassAssignments/UserClassAssignments.vue'
import UserCourseAssignments from '@/components/users/UserCourseAssignments/UserCourseAssignments.vue'
import UserProjectAssignments from '@/components/users/UserProjectAssignments/UserProjectAssignments.vue'
const workspace = useUsersManagement()
provide(usersManagementKey, workspace)
const { session, op, selected } = workspace
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">Администрирование</p>
      <h1>Учётные записи</h1>
      <p class="subtitle">Профили пользователей, классы, курсы и проекты.</p>
    </div>
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <template v-if="session.institutionAdmin"
    ><UserStudentAssignment /><UserDirectory />
    <section v-if="selected" class="panel user-card">
      <UserProfile />
      <div class="assignment-grid">
        <UserClassAssignments /><UserCourseAssignments /><UserProjectAssignments />
      </div>
      <p class="helper">Последнее изменение: {{ formatDateTime(selected.updated_at) }}</p>
    </section></template
  >
  <p v-else>Управление учётными записями доступно администраторам.</p>
</template>
<style src="./UsersView.css" scoped></style>
