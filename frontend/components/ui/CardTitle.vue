<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <h3 data-slot="card-title" :class="cn('text-sm font-bold text-foreground', props.class)">
    <slot />
  </h3>
</template>
