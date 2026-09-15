<script setup lang="ts">
import { ChevronDown, LogOut } from "lucide-vue-next";

const ROLE_LABELS: Record<string, string> = {
  VIEWER: "Visualizador",
  ANALYST: "Analista",
  ADMIN: "Administrador",
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

const { store, logout } = useAuth();
const open = ref(false);
const rootRef = ref<HTMLElement | null>(null);

function onClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node))
    open.value = false;
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener("mousedown", onClickOutside);
  else document.removeEventListener("mousedown", onClickOutside);
});
onBeforeUnmount(() =>
  document.removeEventListener("mousedown", onClickOutside),
);

async function handleLogout() {
  open.value = false;
  await logout();
}
</script>

<template>
  <div ref="rootRef" class="relative">
    <button
      type="button"
      aria-haspopup="menu"
      :aria-expanded="open"
      class="flex items-center gap-1.5 rounded-full py-0.5 pl-0.5 pr-1.5 transition-colors hover:bg-muted"
      @click="open = !open"
    >
      <span
        class="relative flex size-10 items-center justify-center rounded-full bg-primary/10 text-[13px] font-bold text-primary"
      >
        {{ initials(store.user?.name || "?") }}
        <span
          class="absolute bottom-0 right-0 size-2.5 rounded-full border-2 border-background bg-success"
        />
      </span>
      <ChevronDown class="size-3.5 text-muted-foreground" />
    </button>

    <div
      v-if="open"
      role="menu"
      class="absolute right-0 top-[calc(100%+8px)] z-20 w-56 rounded-xl border border-border bg-popover p-1.5 text-popover-foreground shadow-lg"
    >
      <div class="px-2.5 py-2">
        <p class="truncate text-sm font-bold text-foreground">
          {{ store.user?.name }}
        </p>
        <p class="text-xs text-muted-foreground">
          {{ store.user ? ROLE_LABELS[store.user.role] : "" }}
        </p>
      </div>

      <div class="my-1 h-px bg-border" />

      <button
        type="button"
        class="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
        @click="handleLogout"
      >
        <LogOut class="size-4" />
        Sair
      </button>
    </div>
  </div>
</template>
