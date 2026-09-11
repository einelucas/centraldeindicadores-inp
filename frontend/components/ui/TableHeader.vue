<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <thead data-slot="table-header" :class="cn('bg-muted/60 [&_tr]:border-b', props.class)">
    <slot />
  </thead>
</template>
