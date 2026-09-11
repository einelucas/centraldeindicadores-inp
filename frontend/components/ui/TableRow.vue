<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <tr
    data-slot="table-row"
    :class="cn('border-b border-border transition-colors last:border-0 hover:bg-muted/40', props.class)"
  >
    <slot />
  </tr>
</template>
