<script setup>
import { watch } from 'vue';

const props = defineProps({
  chat: {
    type: Object,
    required: true,
  },
});

// Watch for changes in chat to fetch new info if needed (the description and function are wrong)
watch(
  () => props.chat.id,
  (newChatId, oldChatId) => {
    if (newChatId) {
      console.log(`Chat changed to: ${newChatId} from ${oldChatId}. Fetching messages...`);
      // --- TODO: Add logic here to fetch info for newChatId ---
      // e.g., fetch(`/api/chats/${newChatId}/messages`)
    } else {
      // Clear messages if no chat is selected
    }
  },
);
</script>

<template>
  <div class="info-wrapper">
    <h2>Данные клиента</h2>
    <ul class="info">
      <li>8-916-999-99-XX</li>
      <li>Абонент МТС: да</li>
      <li>Тариф: Конвергентный тарифный план Тариф №7 (мобильная связь</li>
      <li>МТС + домашний интернет + ТВ)</li>
      <li>Мобильная связь: есть</li>
      <li>Домашний интернет: есть</li>
      <li>Домашнее ТВ: есть</li>
      <li>Домашний телефон: нет</li>
      <li>Устройство: iPhone 16 pro 256 GB</li>
      <li>ОС: iOS, версия 18.4</li>
      <li>Пользователь приложения Мой МТС: да</li>
      <li>Пользователь Личный кабинет: нет</li>
      <li>Пользователь приложения МТС Банк: да</li>
      <li>Пользователь приложения МТС Деньги: нет</li>
      <li>Подписки и сервисы на номере: нет</li>
      <li>МТС Premium: есть</li>
      <li>МТС Cashback: есть</li>
      <li>Защитник базовый: есть</li>
      <li>Защитник+: нет</li>
      <li>Отдельная подписка Kion: нет</li>
      <li>Отдельная подписка Музыка: нет</li>
      <li>Отдельная подписка Строки: нет</li>
      <li>Дебетовая карта МТС Банк: есть</li>
      <li>Кредитная карта МТС Банк: нет</li>
      <li>Дебетовая карта МТС Деньги: нет</li>
      <li>Кредитная карта МТС Деньги: нет</li>
      <li>Виртуальная карта МТС Деньги: нет</li>
    </ul>
  </div>
</template>

<style scoped>
.info-wrapper {
  font-family: Arial;
  overflow-y: auto;
  height: 30%;
  background-color: var(--grey);
  padding: 1rem;
}
h2 {
  font-size: 1.1rem;
  font-family: Arial;
}
ul {
  padding: 0;
  list-style-type: none;
}
</style>
