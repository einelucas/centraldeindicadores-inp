<script setup lang="ts">
definePageMeta({ middleware: "auth" });
const auth = useAuthStore();
</script>

<template>
  <ModuleWorkspace
    eyebrow="Planejamento · RNC"
    title="Não Conformidades"
    description="Painel de acompanhamento das RNCs e do tempo de tratativa por unidade."
    :has-administration="auth.user?.role !== 'VIEWER'"
  >
    <template #panel><RncPublishedPanel /></template>
    <template #administration>
      <RncAdmin :can-publish="auth.isAdmin" :can-clear="auth.isAdmin" />
    </template>
  </ModuleWorkspace>
</template>
