<script setup lang="ts">
import LoginForm from '@/components/auth/LoginForm/LoginForm.vue'
</script>
<template>
  <section class="login-view panel" aria-labelledby="login-title">
    <h1 id="login-title">Вход</h1>
    <LoginForm />
    <p class="login-switch">Нет аккаунта? <RouterLink to="/register">Регистрация</RouterLink></p>
  </section>
</template>
<style src="./LoginView.css" scoped></style>
