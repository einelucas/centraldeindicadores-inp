<script setup lang="ts">
import { AlertTriangle, CalendarCheck, ChartColumn, HardHat, LayoutDashboard, ListChecks } from "lucide-vue-next";

const route = useRoute();
const tabs = [
  { label: "Scorecard", href: "/dashboard/scorecard", icon: LayoutDashboard },
  { label: "RDO", href: "/dashboard/rdo", icon: ChartColumn },
  { label: "IDP - Disciplinas", href: "/dashboard/idp", icon: CalendarCheck },
  { label: "RNC", href: "/dashboard/rnc", icon: AlertTriangle },
  { label: "5S", href: "/dashboard/cinco-s", icon: ListChecks },
  { label: "Taxa de Acidentes", href: "/dashboard/taxa-acidentes", icon: HardHat },
];
</script>

<template>
  <div class="app-toolbar-shell pt-2.5">
    <nav class="flex items-center gap-2 overflow-x-auto rounded-[18px] border border-[#e7ecf3] bg-white px-4 py-3 shadow-[0_10px_30px_rgba(39,69,120,0.08)]" aria-label="Indicadores">
      <NuxtLink
        v-for="tab in tabs" :key="tab.href" :to="tab.href" :aria-label="tab.label" :title="tab.label"
        class="flex size-11 shrink-0 items-center justify-center rounded-[14px] border border-transparent text-slate-500 transition-colors hover:border-slate-200 hover:bg-slate-50"
        :class="route.path.startsWith(tab.href) ? '!border-[#d8e5ff] !bg-[#edf3ff] !text-[#21427d]' : ''"
      >
        <component :is="tab.icon" :size="20" :stroke-width="2" />
      </NuxtLink>
      <div id="workspace-actions" class="ml-auto flex shrink-0 items-center gap-2" />
    </nav>
  </div>
</template>
