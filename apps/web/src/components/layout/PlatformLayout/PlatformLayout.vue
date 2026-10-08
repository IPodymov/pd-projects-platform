<script setup lang="ts">
import { ref } from 'vue'
import PlatformSidebar from '../PlatformSidebar/PlatformSidebar.vue'
const menu = ref(false)
</script>
<template>
  <div class="platform-layout">
    <PlatformSidebar :open="menu" @close="menu = false" />
    <div class="platform-workspace">
      <header class="platform-mobile-header">
        <button type="button" aria-label="Открыть меню" :aria-expanded="menu" @click="menu = !menu">
          <i class="pi pi-bars" /></button
        ><RouterLink to="/">Проектория</RouterLink>
      </header>
      <main class="platform-main" id="main-content"><slot /></main>
    </div>
  </div>
</template>
<style src="./PlatformLayout.css" scoped></style>
