<script setup>
import AgentHelp from './AgentHelp.vue';
import ChatWindow from './ChatWindow.vue';
import ClientInfo from './ClientInfo.vue';

// Define props received from App.vue
const props = defineProps({
  chat: {
    type: [Object, null],
    default: null,
  },
});
</script>

<template>
  <div class="operator-interface">
    <div v-if="!chat" class="placeholder">Выберите чат для начала общения</div>
    <template v-else>
      <div class="left-side">
        <ChatWindow :chat="chat" />
        <ClientInfo :chat="chat" />
      </div>
      <div class="right-side">
        <AgentHelp :chat="chat" />
        <div class="message-input">
          <input type="text" placeholder="Сообщение..." />
          <button>Отправить</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.operator-interface {
  flex-grow: 1; /* Take remaining horizontal space */
  display: flex;
  height: 100%;
  background-color: var(--whitish);
  color: var(--dark);
}

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  flex-grow: 1;
}

.left-side,
.right-side {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.left-side {
  width: 30%;
  border-right: 5px solid var(--grey);
}

.right-side {
  width: 70%;
}

.message-input {
  display: flex;
  padding: 1.5rem 1rem;
  background-color: var(--grey);
  margin-top: auto;
  gap: 0.7rem;
}
.message-input input {
  flex-grow: 1;
  padding: 0.3rem 1rem;
  border: none;
  border-radius: 1.1rem;
  background-color: var(--whitish);
}
.message-input button {
  padding: 0.3rem 1rem;
  border: none;
  background-color: var(--red);
  color: var(--white);
  border-radius: 1.1rem;
  cursor: pointer;
}
</style>
