<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <td data-slot="table-cell" :class="cn('px-4 py-2.5 align-middle', props.class)">
    <slot />
  </td>
</template>
