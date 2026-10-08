<script setup lang="ts">
import { inject } from 'vue'
import { usersManagementKey } from '@/composables/useUsersManagement'
import Button from 'primevue/button'
const { session, op, selected, dirty, profile, saveProfile, refreshUser } =
  inject(usersManagementKey)!
</script>
<template>
  <div v-if="selected">
    <div class="actions">
      <h2>{{ selected.name || selected.email }}</h2>
      <Button label="Обновить карточку" text :loading="op.busy.value" @click="refreshUser" />
    </div>
    <p>{{ selected.email }}</p>
    <form class="form" @submit.prevent="saveProfile">
      <label
        >ФИО<input v-model="profile.display_name" required maxlength="200" @input="dirty = true"
      /></label>
      <label
        >Дата рождения<input v-model="profile.date_of_birth" type="date" @input="dirty = true"
      /></label>
      <label v-if="session.user?.platform_admin"
        >Аккаунт активен<input v-model="profile.is_active" type="checkbox" @change="dirty = true"
      /></label>
      <Button type="submit" label="Сохранить профиль" :loading="op.busy.value" />
    </form>
  </div>
</template>
<style src="./UserProfile.css" scoped></style>
