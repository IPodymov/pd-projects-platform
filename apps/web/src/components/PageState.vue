<script setup lang="ts">
import Button from 'primevue/button'
defineProps<{ loading?: boolean; error?: string; empty?: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <div v-if="loading" class="state" role="status">
    <i class="pi pi-spin pi-spinner" /> Загружаем данные…
  </div>
  <div v-else-if="error" class="state error" role="alert">
    <p>{{ error }}</p>
    <Button label="Повторить" severity="secondary" @click="$emit('retry')" />
  </div>
  <div v-else-if="empty" class="state">
    <i class="pi pi-inbox" />
    <h3>Пока ничего нет</h3>
    <p>Записи появятся после назначения или создания.</p>
  </div>
  <slot v-else />
</template>
