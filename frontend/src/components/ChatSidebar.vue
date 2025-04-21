<script setup>
import ChatItem from './ChatItem.vue';

// Define props received from App.vue
const props = defineProps({
  chats: {
    type: Array,
    required: true,
  },
  activeChatId: {
    type: [String, null], // Can be string ID or null
    default: null,
  },
});

// Define emits to send event back up to App.vue
const emit = defineEmits(['select-chat']);

// Method to emit the selected chat ID
function selectChat(chat) {
  emit('select-chat', chat);
}
</script>

<template>
  <div class="chat-sidebar">
    <ul class="chat-list">
      <!-- Iterate over the chats passed as a prop -->
      <ChatItem
        v-for="chat in chats"
        :key="chat.id"
        :chat="chat"
        :isActive="chat.id === activeChatId"
        @click="selectChat(chat)"
      />
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
