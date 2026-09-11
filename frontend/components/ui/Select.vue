<script setup lang="ts">
import { ChevronDown } from "lucide-vue-next";
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
const model = defineModel<string | number>();
</script>

<template>
  <div class="relative">
    <select
      v-model="model"
      data-slot="select"
      :class="
        cn(
          'h-9 w-full appearance-none rounded-lg border border-input bg-background pl-3 pr-8 text-sm font-medium text-foreground shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50',
          props.class,
        )
      "
    >
      <slot />
    </select>
    <ChevronDown class="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
  </div>
</template>
