<script setup lang="ts">
import { LayoutGrid, Settings2 } from "lucide-vue-next";

withDefaults(defineProps<{
  eyebrow: string;
  title: string;
  description: string;
  panelLabel?: string;
  hasAdministration?: boolean;
}>(), { panelLabel: "Painel", hasAdministration: false });

const active = ref<"panel" | "admin">("panel");
</script>

<template>
  <section>
    <ClientOnly>
      <Teleport to="#workspace-actions">
        <div class="workspace-switcher">
          <button type="button" :class="{ active: active === 'panel' }" @click="active = 'panel'">
            <LayoutGrid :size="17" /><span>{{ panelLabel }}</span>
          </button>
          <button v-if="hasAdministration" type="button" :class="{ active: active === 'admin' }" @click="active = 'admin'">
            <Settings2 :size="17" /><span>Administração</span>
          </button>
        </div>
      </Teleport>
    </ClientOnly>

    <header class="module-page-title">
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </header>

    <div v-show="active === 'panel'"><slot name="panel" /></div>
    <div v-if="hasAdministration" v-show="active === 'admin'"><slot name="administration" /></div>
  </section>
</template>
