<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ for?: string; class?: string }>();
</script>

<template>
  <label
    :for="props.for"
    data-slot="label"
    :class="cn('text-[11px] font-bold uppercase tracking-wide text-muted-foreground', props.class)"
  >
    <slot />
  </label>
</template>
