<script setup lang="ts">
const route = useRoute();
const showShell = computed(() => !route.meta.publicLayout);
</script>

<template>
  <div v-if="showShell" class="min-h-screen bg-[#f4f5f7]">
    <AppHeader />
    <TabsNav />
    <main class="nuxt-app-main"><slot /></main>
    <footer class="pb-8 text-center text-xs text-slate-400">Central de Indicadores</footer>
  </div>
  <slot v-else />
</template>
