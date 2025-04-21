<script setup>
import { ref, watch } from 'vue';
import { getDialog } from '@/api/apiBase';
import { userStore } from "@/store/userStore";

const usersStore = userStore();

const chart = ref([]);
const tiket = ref(0);

const fetchDialog = async () => {
  const body = {
    "phone_number": usersStore.currentUser?.phone_number,
    "limit": 50
  };

  try {
    const result = await getDialog(body);
    const length = chart.value.length;

    if (length !== 0 && length === result.data?.history.length && length < 50) {
      return;
    }

    chart.value = result.data?.history ?? [];
    if(chart.value.length !== 0) usersStore.updateAnalize();
  } catch {
    chart.value = [];
  }
};

watch(() => usersStore.currentUser, () => {
  clearTimeout(tiket.value);
  chart.value = [];
  fetchDialog();

  tiket.value = setInterval(() => {
    fetchDialog();
  }, 3000);
});

fetchDialog();

tiket.value = setInterval(() => {
  fetchDialog();
}, 3000);
</script>

<template>
  <div class="chat-content">
    <ul class="message-list">
      <li v-for="(item, idx) in chart" :key="idx" class="msg"
        :class="{ operator: item.role === 'assistant', client: item.role === 'user' }">
        {{ item.role === 'user'? item.user_text : item.operator_response }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.chat-content {
  display: flex;
  flex-direction: column;
  height: 70%;
  border-bottom: 3px solid var(--grey);
}

.message-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1rem;
  list-style-type: none;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.msg {
  padding: 0.8rem;
  border-radius: 1.2rem;
}

.msg.client {
  background-color: var(--grey);
  margin-right: 10%;
}

.msg.operator {
  background-color: var(--red);
  color: var(--whitish);
  margin-left: 10%;
}
</style>
