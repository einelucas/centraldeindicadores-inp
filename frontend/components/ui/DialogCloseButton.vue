<script setup lang="ts">
import { X } from "lucide-vue-next";

defineEmits<{ click: [] }>();
</script>

<template>
  <button
    type="button"
    class="shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    aria-label="Fechar"
    @click="$emit('click')"
  >
    <X class="size-4" />
  </button>
</template>
