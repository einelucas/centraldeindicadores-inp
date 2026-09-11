<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ ok: boolean; class?: string }>();
</script>

<template>
  <span
    :class="
      cn(
        'inline-block rounded-full px-2 py-0.5 text-xs font-semibold',
        props.ok ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger',
        props.class,
      )
    "
  >
    <slot />
  </span>
</template>
