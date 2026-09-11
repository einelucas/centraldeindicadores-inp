<script setup lang="ts">
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "~/utils/cn";

const badgeVariants = cva(
  "inline-flex w-fit items-center gap-1 rounded-full border border-transparent px-2.5 py-0.5 text-[11px] font-bold whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "bg-primary/10 text-primary",
        secondary: "bg-secondary text-secondary-foreground",
        success: "bg-success/10 text-success",
        destructive: "bg-danger/10 text-danger",
        warning: "bg-accent/15 text-accent-foreground",
        outline: "border-border text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

type BadgeVariants = VariantProps<typeof badgeVariants>;

const props = defineProps<{ variant?: BadgeVariants["variant"]; class?: string }>();
</script>

<template>
  <span data-slot="badge" :class="cn(badgeVariants({ variant: props.variant }), props.class)">
    <slot />
  </span>
</template>
