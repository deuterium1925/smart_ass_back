<script setup>
import ChatSidebar from './components/ChatSidebar.vue';
import OperatorInterface from './components/OperatorInterface.vue';

</script>

<template>
  <div class="app-layout">
    <ChatSidebar/>

    <OperatorInterface/>
  </div>
</template>

<style>
.app-layout {
  display: flex;
  height: 100vh;
  background-color: var(--whitish);
  color: var(--grey);
}

</style>
