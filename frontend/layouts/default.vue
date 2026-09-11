<script setup lang="ts">
const route = useRoute();
const showShell = computed(() => !route.meta.publicLayout);
</script>

<template>
  <div v-if="showShell" class="min-h-screen bg-[#f4f5f7]">
    <AppHeader />
    <TabsNav />
    <main class="nuxt-app-main"><slot /></main>
    <footer class="p-6 text-center text-[11.5px] text-[#9aa1ac]">Central de Indicadores - 2026</footer>
  </div>
  <slot v-else />
</template>
