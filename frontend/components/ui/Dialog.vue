<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();

function handleKey(event: KeyboardEvent) {
  if (event.key === "Escape") emit("update:open", false);
}

if (import.meta.client) {
  watch(
    () => props.open,
    (open) => {
      if (open) document.addEventListener("keydown", handleKey);
      else document.removeEventListener("keydown", handleKey);
    },
  );
  onBeforeUnmount(() => document.removeEventListener("keydown", handleKey));
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="fixed inset-0 bg-black/40" aria-hidden="true" @click="emit('update:open', false)" />
      <div class="relative z-10 w-full max-w-md">
        <slot />
      </div>
    </div>
  </Teleport>
</template>
