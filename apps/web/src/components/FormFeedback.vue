<script setup lang="ts">
defineProps<{ error?: string; fields?: Record<string, string[]>; success?: string }>()
const labels: Record<string, string> = {
  non_field_errors: 'Общая ошибка',
  text: 'Результат',
  feedback: 'Замечание',
  remarks: 'Замечание',
  previous: 'Предыдущая отправка',
  title: 'Название',
  due_at: 'Срок',
  classroom: 'Класс',
  email: 'Почта',
  users: 'Участники',
  online_url: 'Онлайн-ссылка',
  location: 'Место',
  reviewer: 'Проверяющий',
  institution: 'Учреждение',
  milestone: 'Этап',
  criteria: 'Критерии',
  assignment: 'Задание',
}
</script>
<template>
  <div v-if="error" class="state error" role="alert">
    <p>{{ error }}</p>
    <ul v-if="fields">
      <li v-for="(messages, key) in fields" :key="key">
        {{ labels[key] || key }}: {{ messages.join(' · ') }}
      </li>
    </ul>
  </div>
  <p v-if="success" class="helper" role="status">{{ success }}</p>
</template>
