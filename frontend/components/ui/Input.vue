<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ type?: string; class?: string }>();
const model = defineModel<string | number>();
</script>

<template>
  <input
    v-model="model"
    :type="props.type ?? 'text'"
    data-slot="input"
    :class="
      cn(
        'flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm font-medium text-foreground shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )
    "
  />
</template>
