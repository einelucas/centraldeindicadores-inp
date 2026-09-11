<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <th
    data-slot="table-head"
    :class="
      cn(
        'h-10 whitespace-nowrap px-4 text-left align-middle text-[11px] font-bold uppercase tracking-wide text-muted-foreground',
        props.class,
      )
    "
  >
    <slot />
  </th>
</template>
