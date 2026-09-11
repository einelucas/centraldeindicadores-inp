<script setup lang="ts">
import type { Component } from "vue";
import { cn } from "~/utils/cn";

const props = withDefaults(
  defineProps<{
    label: string;
    value: string;
    sub?: string;
    icon: Component;
    tone?: "default" | "success" | "warning" | "destructive";
    valueClass?: string;
  }>(),
  { tone: "default", sub: undefined, valueClass: undefined },
);

const toneClass = computed(() =>
  props.tone === "success" ? "text-success"
  : props.tone === "warning" ? "text-accent"
  : props.tone === "destructive" ? "text-danger"
  : "text-foreground",
);
const iconClass = computed(() => (props.tone === "default" ? "text-muted-foreground" : toneClass.value));
</script>

<template>
  <Card class="flex flex-row items-start justify-between gap-3 p-4">
    <div class="min-w-0">
      <div class="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">{{ label }}</div>
      <div :class="cn('mt-1.5 text-2xl font-extrabold', toneClass, valueClass)">{{ value }}</div>
      <div v-if="sub" class="mt-0.5 text-[11px] text-muted-foreground">{{ sub }}</div>
      <div v-if="$slots.badge" class="mt-1.5"><slot name="badge" /></div>
    </div>
    <component :is="icon" :class="cn('size-4 shrink-0', iconClass)" />
  </Card>
</template>
