<script setup lang="ts">
import { cn } from "~/utils/cn";

const props = defineProps<{ class?: string }>();
</script>

<template>
  <div data-slot="card-content" :class="cn('p-5 pt-0', props.class)">
    <slot />
  </div>
</template>
