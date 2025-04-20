<script setup>
import avatarSrc from '@/icons/user.svg';

// Define props received from ChatSidebar.vue
const props = defineProps({
  chat: {
    type: Object,
    required: true,
  },
  isActive: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <li class="chat-item" :class="{ active: isActive }">
    <div class="avatar"><img :src="avatarSrc" /></div>
  </li>
</template>

<style scoped>
.chat-item {
  display: flex;
  align-items: center;
  flex-direction: center;
  padding: 0.6rem;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.chat-item:hover {
  background-color: var(--red); /* Hover effect */
}

.chat-item.active {
  background-color: var(--red); /* Active chat highlight */
}

.avatar {
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  background: var(--light-grey);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
