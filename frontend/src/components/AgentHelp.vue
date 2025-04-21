<script setup>
import { watch } from 'vue';

const props = defineProps({
  chat: {
    type: Object,
    required: true,
  },
});

// Watch for changes in chat to fetch new AI suggestions as the conversation progresses (the description and function are wrong)
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
  <div class="agent-help">
    <div class="operator-performance">
      <span class="embolden">Характер диалога:</span> ты тупой? Не будь как робот, разговаривай
      по-человечески. Иначе пойдёшь улицы подметать. Или того хуже — фронтенд делать.
    </div>
    <div class="client-emotion">
      <span class="embolden">Настроение:</span> Клиент тебя ненавидит.
    </div>
    <ul class="suggestions">
      <li>
        First of all, I am really sorry I confused you by my greeting! Second, I can assure you that
        I am a real person. Tell me, please, what is your issue? I will be happy to help you!
      </li>
      <li>Maybe you are a robot? Why are you so rude? I just want to help.</li>
      <li>
        Пошёл к чёрту, я не говорю на английском. Это МТС, motherfucker, так что пиши на русском.
      </li>
    </ul>
    <div class="recommended">
      <span class="embolden">Рекомендуемый ответ:</span> First of all, I am really sorry I confused
      you by my greeting! Second, I can assure you that I am a real person. Tell me, please, what is
      your issue? I will be happy to help you!
    </div>
  </div>
</template>

<style scoped>
.agent-help {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.3rem;
  padding: 1rem;
  & > *:not(.suggestions),
  .suggestions > li {
    background-color: var(--grey);
    padding: 0.8rem;
    border-radius: 1.2rem;
  }
}
.embolden {
  font-weight: 700;
}
.suggestions {
  padding: 0;
  list-style-type: none;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: auto;
  & > li {
    width: 31%;
  }
}
</style>
