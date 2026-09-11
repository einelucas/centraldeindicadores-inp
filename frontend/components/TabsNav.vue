<script setup lang="ts">
import { AlertTriangle, CalendarCheck, ChartColumn, Clock, LayoutDashboard, ListChecks } from "lucide-vue-next";

const route = useRoute();
const tabs = [
  { label: "Scorecard", href: "/dashboard/scorecard", icon: LayoutDashboard },
  { label: "RDO", href: "/dashboard/rdo", icon: ChartColumn },
  { label: "IDP - Disciplinas", href: "/dashboard/idp", icon: CalendarCheck },
  { label: "RNC", href: "/dashboard/rnc", icon: AlertTriangle },
  { label: "Horas Extras", href: "/dashboard/horas-extras", icon: Clock },
  { label: "5S", href: "/dashboard/cinco-s", icon: ListChecks },
];

const hoveredTab = ref<(typeof tabs)[number] | null>(null);
const tooltipStyle = ref({ top: "0px", left: "0px" });

function showTooltip(event: MouseEvent, tab: (typeof tabs)[number]) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
  tooltipStyle.value = { top: `${rect.bottom + 8}px`, left: `${rect.left + rect.width / 2}px` };
  hoveredTab.value = tab;
}

function hideTooltip() {
  hoveredTab.value = null;
}
</script>

<template>
  <div class="app-toolbar-shell pt-2.5">
    <nav
      id="tabsNav"
      class="flex items-center gap-2 overflow-x-auto rounded-[18px] border border-[#e7ecf3] bg-background px-4 py-3 shadow-[0_10px_30px_rgba(39,69,120,0.08)]"
      aria-label="Indicadores"
    >
      <NuxtLink
        v-for="tab in tabs"
        :key="tab.href"
        :to="tab.href"
        :aria-label="tab.label"
        class="flex size-11 shrink-0 items-center justify-center rounded-[14px] border border-transparent text-muted-foreground transition-colors"
        :class="
          route.path === tab.href || route.path.startsWith(`${tab.href}/`)
            ? 'border-[#d8e5ff] bg-[#edf3ff] text-[#21427d]'
            : 'hover:border-border hover:bg-muted/60 hover:text-foreground'
        "
        @mouseenter="showTooltip($event, tab)"
        @mouseleave="hideTooltip"
        @click="hideTooltip"
      >
        <component :is="tab.icon" class="size-5" :stroke-width="2" />
      </NuxtLink>

      <div id="workspace-actions" class="ml-auto flex shrink-0 items-center gap-2" />
    </nav>

    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-150 ease-out"
        enter-from-class="opacity-0 scale-90"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-100 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-90"
      >
        <span
          v-if="hoveredTab"
          role="tooltip"
          class="pointer-events-none fixed z-50 -translate-x-1/2 whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1.5 text-xs font-semibold text-background shadow-lg"
          :style="tooltipStyle"
        >
          <span aria-hidden="true" class="absolute -top-1 left-1/2 size-2 -translate-x-1/2 rotate-45 bg-foreground" />
          {{ hoveredTab.label }}
        </span>
      </Transition>
    </Teleport>
  </div>
</template>
