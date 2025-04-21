import { defineStore } from 'pinia';
import { ref } from 'vue';

export const userStore = defineStore('user-store', () => {
  const users = ref([]);
  const currentUser = ref(null);
  // const userDialog = ref(null);
  const updatetAnalize = ref(Symbol());

  const isLoading = ref(false);
  const setUser = (index) => {
    const user = users.value[index];
    currentUser.value = user;
  }

  const setUsers = (userArr) => {
    users.value = userArr;
  }

  const updateAnalize = () => {
    updatetAnalize.value = Symbol();
  }

  const updateLoading = (update = false) => {
    isLoading.value = update
  };

  return { users, currentUser, setUsers, setUser, updatetAnalize, updateAnalize, isLoading, updateLoading };
});
