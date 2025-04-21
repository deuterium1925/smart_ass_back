<script setup>
import { userStore } from "@/store/userStore";

const usersStore = userStore();
const endStr = "XX";

const isPresen = (state) => {
  return state ? 'есть' : 'нет';
};

const isTrust = (state) => {
  return state ? 'да' : 'нет';
}

</script>

<template>
  <div class="info-wrapper">
    <h2>Данные клиента</h2>

    {{ tt }}

    <ul class="info">
      <li>{{ usersStore.currentUser?.phone_number?.slice(0, -2) + `-${endStr}` }}</li>
      <li>Абонент МТС: {{ isTrust(usersStore.currentUser?.is_mts_subscriber) }}</li>

      <li>Тариф: {{ usersStore.currentUser?.tariff_plan }}</li>
      <li>МТС + домашний интернет + ТВ)</li>

      <li>Мобильная связь: {{ isPresen(usersStore.currentUser?.has_mobile) }}</li>
      <li>Домашний интернет: {{ isPresen(usersStore.currentUser?.has_home_internet) }}</li>
      <li>Домашнее ТВ: {{ isPresen(usersStore.currentUser?.has_home_tv) }}</li>
      <li>Домашний телефон: {{ isPresen(usersStore.currentUser?.has_home_phone) }}</li>
      <li>Устройство: {{ usersStore.currentUser?.device }}</li>
      <li>ОС: {{ usersStore.currentUser?.os }}</li>
      <li>Пользователь приложения Мой МТС: {{ isTrust(usersStore.currentUser?.uses_my_mts_app) }}</li>
      <li>Пользователь Личный кабинет: {{ isTrust(usersStore.currentUser?.uses_personal_account) }}</li>
      <li>Пользователь приложения МТС Банк: {{ isTrust(usersStore.currentUser?.uses_mts_bank_app) }}</li>
      <li>Пользователь приложения МТС Деньги: {{ isTrust(usersStore.currentUser?.uses_mts_money_app) }}</li>
      <li>Подписки и сервисы на номере: {{ isPresen(usersStore.currentUser?.subscriptions_and_services) }}</li>
      <li>МТС Premium: {{ isPresen(usersStore.currentUser?.has_mts_premium) }}</li>
      <li>МТС Cashback: {{ isPresen(usersStore.currentUser?.has_mts_cashback) }}</li>
      <li>Защитник базовый: {{ isPresen(usersStore.currentUser?.has_defender_basic) }}</li>
      <li>Защитник+: {{ isPresen(usersStore.currentUser?.has_defender_plus) }}</li>
      <li>Отдельная подписка Kion: {{ isPresen(usersStore.currentUser?.has_kion_subscription) }}</li>
      <li>Отдельная подписка Музыка: {{ isPresen(usersStore.currentUser?.has_music_subscription) }}</li>
      <li>Отдельная подписка Строки: {{ isPresen(usersStore.currentUser?.has_strings_subscription) }}</li>
      <li>Дебетовая карта МТС Банк: {{ isPresen(usersStore.currentUser?.has_mts_bank_debit_card) }}</li>
      <li>Кредитная карта МТС Банк: {{ isPresen(usersStore.currentUser?.has_mts_bank_credit_card) }}</li>
      <li>Дебетовая карта МТС Деньги: {{ isPresen(usersStore.currentUser?.has_mts_money_debit_card) }}</li>
      <li>Кредитная карта МТС Деньги: {{ isPresen(usersStore.currentUser?.has_mts_money_credit_card) }}</li>
      <li>Виртуальная карта МТС Деньги: {{ isPresen(usersStore.currentUser?.has_mts_money_virtual_card) }}</li>
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
