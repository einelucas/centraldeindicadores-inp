<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <div data-slot="card" :class="cn('rounded-xl border border-border bg-card text-card-foreground shadow-sm', props.class)">
    <slot />
  </div>
</template>
