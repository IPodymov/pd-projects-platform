<script setup lang="ts">
import RegistrationForm from '@/components/auth/RegistrationForm/RegistrationForm.vue'
</script>
<template>
  <section class="register-view panel" aria-labelledby="register-title">
    <h1 id="register-title">Регистрация</h1>
    <RegistrationForm />
    <p class="register-switch">Уже есть аккаунт? <RouterLink to="/login">Войти</RouterLink></p>
  </section>
</template>
<style src="./RegisterView.css" scoped></style>
