<script setup lang="ts">
definePageMeta({ publicLayout: true });const {completeLogin}=useAuth();const error=ref("");onMounted(async()=>{try{await completeLogin();await navigateTo("/dashboard/scorecard");}catch(cause){error.value=cause instanceof Error?cause.message:"Falha ao concluir autenticação.";}});
</script>
<template><div class="grid min-h-screen place-items-center bg-slate-100"><div class="text-center"><div v-if="!error" class="spinner mx-auto"/><h1 class="mt-4 text-xl font-extrabold text-brand-dark">Concluindo autenticação</h1><p v-if="error" class="notice error mt-3">{{error}}</p><NuxtLink v-if="error" class="btn mt-3" to="/login">Voltar ao login</NuxtLink></div></div></template>
