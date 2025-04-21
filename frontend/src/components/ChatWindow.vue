<script setup>
import { watch } from 'vue';

const props = defineProps({
  chat: {
    type: Object,
    required: true,
  },
});

// Watch for changes in chatId to fetch messages
watch(
  () => props.chat.id,
  (newChatId, oldChatId) => {
    if (newChatId) {
      console.log(`Chat changed to: ${newChatId} from ${oldChatId}. Fetching messages...`);
      // --- TODO: Add logic here to fetch messages for newChatId ---
      // e.g., fetch(`/api/chats/${newChatId}/messages`)
    } else {
      // Clear messages if no chat is selected
    }
  },
);
</script>

<template>
  <div class="chat-content">
    <ul class="message-list">
      <!-- <li v-for="msg of msgs"></li> -->
      <li class="msg client">
        Hi! Help me! I'm completely lost in your stupid graphical user interface. How do I get out?
      </li>
      <li class="msg operator">Hello, Sir! How can I help you?</li>
      <li class="msg client">
        Are you a robot? You bastard, stupid robot, ask a human operator to talk to me. I don't want
        to have a convo with no damn robot.
      </li>
      <li class="msg client">
        Are you a robot? You bastard, stupid robot, ask a human operator to talk to me. I don't want
        to have a convo with no damn robot.
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
