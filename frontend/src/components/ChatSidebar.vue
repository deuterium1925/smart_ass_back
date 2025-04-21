<script setup>
import { ref, onMounted } from 'vue';
import ChatItem from './ChatItem.vue';
import { getUser } from '@/api/apiBase'
import { userStore } from "@/store/userStore";

const usersStore = userStore();
const selectedIndex = ref(null);

function selectChat(index) {
  selectedIndex.value = index;
  usersStore.setUser(index);
}

const phonesUser = ['89111111111', '89123456789', '89169999933'];

onMounted(async () => {
  const promise = phonesUser.map((el) => getUser(el))

  const result = await Promise.allSettled(promise);

  const userArr = [];
  result.forEach(element => {
    if (element.status === 'fulfilled') {
      userArr.push(element.value?.data?.customer)
    }
  });

  usersStore.setUsers(userArr);
});
</script>

<template>
  <div class="chat-sidebar">
    <ul class="chat-list">
      <ChatItem v-for="(user, idx) in usersStore.users" :key="idx" :chat="user" :isActive="idx === selectedIndex"
        @click="selectChat(idx)" />
    </ul>
  </div>
</template>

<style scoped>
.chat-sidebar {
  background-color: var(--dark);
}

.chat-list {
  list-style: none;
  padding: 0;
  margin: 0;
  flex-grow: 1;
  overflow-y: auto;
  scrollbar-width: none;
}
</style>
