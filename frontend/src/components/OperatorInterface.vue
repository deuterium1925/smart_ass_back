<script setup>
import AgentHelp from './AgentHelp.vue';
import ChatWindow from './ChatWindow.vue';
import ClientInfo from './ClientInfo.vue';
import { userStore } from "@/store/userStore";
import { ref } from 'vue'
import { sendDialog } from '@/api/apiBase';

const usersStore = userStore();
const value = ref('');


const sendMessage = async () => {
  if (usersStore.isLoading || value.value === '') return

  try {
    await sendDialog({
      "phone_number": usersStore.currentUser?.phone_number,
      "operator_response": value.value
    });

    value.value = '';
  } catch {
    console.error('error sending');
  }
};
</script>

<template>
  <div class="operator-interface">
    <div v-if="!usersStore.currentUser" class="placeholder">Выберите чат для начала общения</div>

    <template v-else>
      <div class="left-side">
        <ChatWindow />

        <ClientInfo />
      </div>

      <div class="right-side">
        <AgentHelp />

        <div class="message-input">
          <input type="text" placeholder="Сообщение..." v-model="value" />

          <button :class="{ 'disabled': usersStore.isLoading }" :disabled="usersStore.isLoading"
            @click="sendMessage">Отправить</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.operator-interface {
  flex-grow: 1;
  /* Take remaining horizontal space */
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

.message-input .disabled {
  background: #595959;
}
</style>
