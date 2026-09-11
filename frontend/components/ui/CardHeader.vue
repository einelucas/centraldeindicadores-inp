<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <div data-slot="card-header" :class="cn('flex flex-col gap-1.5 p-5', props.class)">
    <slot />
  </div>
</template>
