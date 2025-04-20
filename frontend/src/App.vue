<script setup>
import { ref, onMounted, computed } from 'vue';
import ChatSidebar from './components/ChatSidebar.vue';
import OperatorInterface from './components/OperatorInterface.vue';

// --- State ---

// Reactive array to hold the chat list
// API or WebSocket!
const chatList = ref([
  {
    id: 'chat1',
    name: 'Alice',
  },
  {
    id: 'group1',
    name: 'Vue Developers',
  },
  {
    id: 'chat2',
    name: 'Bob',
  },
  {
    id: 'chat3',
    name: 'Charlie',
  },
  // ... more chats
]);

// Reactive variable to store the ID of the currently selected chat
const selectedChat = ref(null); // Initially no chat is selected

// --- Methods ---

// Function to update the selected chat ID
function handleSelectChat(chat) {
  console.log('Selected Chat ID:', chat.id);
  selectedChat.value = chat;
  // Fetch chat details
}

// --- Lifecycle ---
onMounted(() => {
  // Fetch initial chat list here if needed
  // fetch('/api/chats').then(res => res.json()).then(data => chatList.value = data);
});
</script>

<template>
  <div class="app-layout">
    <ChatSidebar
      :chats="chatList"
      :activeChatId="selectedChat ? selectedChat.id : selectedChat"
      @select-chat="handleSelectChat"
    />
    <OperatorInterface :chat="selectedChat" />
  </div>
</template>

<style>
/* Basic Layout Styling */
.app-layout {
  display: flex;
  height: 100vh; /* Full viewport height */
  background-color: var(--whitish);
  color: var(--grey);
}

/* Ensure components take up space */
/* ChatSidebar will have its own width */
/* OperatorInterface should grow */
</style>
