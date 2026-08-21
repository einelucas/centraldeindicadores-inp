<script setup lang="ts">
withDefaults(defineProps<{ label: string; value: string; detail?: string; tone?: "default" | "good" | "bad" }>(), {
  detail: "",
  tone: "default",
});
</script>

<template>
  <article class="metric-card" :class="tone">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="detail" class="detail">{{ detail }}</div>
  </article>
</template>
