<script setup lang="ts">
import { Check } from "lucide-vue-next";
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
const model = defineModel<boolean>({ default: false });
</script>

<template>
  <span class="relative inline-flex size-4 shrink-0">
    <input
      v-model="model"
      type="checkbox"
      data-slot="checkbox"
      :class="
        cn(
          'peer size-4 shrink-0 appearance-none rounded border border-input bg-background transition-colors checked:border-primary checked:bg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50',
          props.class,
        )
      "
    />
    <Check
      class="pointer-events-none absolute inset-0 size-4 scale-0 text-primary-foreground transition-transform peer-checked:scale-100"
      :stroke-width="3"
    />
  </span>
</template>
