<script setup lang="ts">
definePageMeta({ middleware: "auth" });

const auth = useAuthStore();
</script>

<template>
  <ModuleWorkspace
    eyebrow="RH · Horas Extras"
    title="Horas Extras Pagas"
    description="Acompanhamento do percentual de horas extras pagas por unidade e período."
    :has-administration="auth.user?.role !== 'VIEWER'"
  >
    <template #panel>
      <HorasExtrasPublishedPanel />
    </template>

    <template #administration>
      <HorasExtrasAdmin />
    </template>
  </ModuleWorkspace>
</template>
