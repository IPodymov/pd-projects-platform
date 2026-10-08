<template>
  <div class="auth-layout">
    <aside class="auth-intro">
      <RouterLink to="/" class="auth-brand">Проектория</RouterLink>
      <div class="auth-intro-content">
        <h1>Индивидуальные проекты: от темы до защиты</h1>
        <p>
          Загружайте работы, получайте комментарии преподавателей и следите за историей изменений.
        </p>
      </div>
      <p class="auth-audience">Для учеников, преподавателей, кураторов и администраторов</p>
    </aside>
    <main id="main-content" class="auth-main"><slot /></main>
  </div>
</template>
<style src="./AuthLayout.css" scoped></style>
