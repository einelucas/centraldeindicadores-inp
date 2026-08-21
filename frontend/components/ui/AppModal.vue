<script setup lang="ts">
defineProps<{ open: boolean; title: string }>();
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" role="dialog" aria-modal="true" @click.self="emit('close')">
      <section class="modal-card">
        <header class="modal-header"><h2>{{ title }}</h2><button class="btn small" @click="emit('close')">Fechar</button></header>
        <div class="modal-body"><slot /></div>
        <footer v-if="$slots.actions" class="modal-actions"><slot name="actions" /></footer>
      </section>
    </div>
  </Teleport>
</template>
