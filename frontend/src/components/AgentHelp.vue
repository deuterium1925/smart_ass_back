<script setup>
import { ref, watch } from 'vue';
import { getAnalyze } from '@/api/apiBase';
import { userStore } from "@/store/userStore";

const usersStore = userStore();
const suggestions = ref([]);
const feedback = ref('');
const intent = ref('');
const emotion = ref('');

const fetchAnalyze = async () => {
  usersStore.updateLoading(true);

  const body = {
    "phone_number": usersStore.currentUser?.phone_number,
    "history_limit": 1
  };

  try {
    const result = await getAnalyze(body);
    suggestions.value = result.data?.suggestions ?? [];
    feedback.value = result.data?.qa_feedback?.result?.feedback ?? '';
    intent.value = result.data?.intent?.result?.intent ?? '';
    emotion.value = result.data?.emotion?.result?.emotion ?? '';
  } catch {
    suggestions.value = [];
    feedback.value = '';
    intent.value = '';
    emotion.value = '';
  } finally {
    usersStore.updateLoading(false);
  }
};

watch(() => usersStore.updatetAnalize, () => {
  suggestions.value = [];
  feedback.value = '';
  intent.value = '';
  emotion.value = '';

  fetchAnalyze();
});
</script>

<template>
  <div class="agent-help">
    {{ usersStore.isUpdate }}
    <div v-if="usersStore.isLoading" class="spinner"></div>

    <template v-else>
      <div v-if="intent" class="operator-performance">
        <span class="embolden">Характер диалога:</span>
        {{ intent }}
      </div>

      <div v-if="emotion" class="client-emotion">
        <span class="embolden">Настроение:</span>
        {{ emotion }}
      </div>

      <ul v-if="suggestions.length !== 0" class="suggestions">
        <li v-for="suggest in suggestions" :key="suggest.priority">
          {{ suggest.text }}
        </li>
      </ul>
    
      <div v-if="feedback" class="recommended">
        <span class="embolden">Рекомендуемый ответ:</span>

        {{ feedback }}
      </div>
    </template>
  </div>
</template>

<style scoped>
.agent-help {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.3rem;
  padding: 1rem;

  &>*:not(.suggestions),
  .suggestions>li {
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

  &>li {
    width: 31%;
  }
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #3498db;
  border-radius: 50%;
  border-bottom-color: transparent;
  /* делаем одну часть прозрачной */
  background: transparent;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  align-self: center;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
