<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <div
    role="dialog"
    aria-modal="true"
    :class="cn('max-h-[85vh] overflow-hidden rounded-xl border border-border bg-card shadow-lg', props.class)"
  >
    <slot />
  </div>
</template>
