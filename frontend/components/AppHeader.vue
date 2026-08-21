<script setup lang="ts">
import { ArrowLeft, Shield, LogOut, UserRound } from "lucide-vue-next";

const router = useRouter();
const { store, logout } = useAuth();
const menuOpen = ref(false);
</script>

<template>
  <header class="flex h-16 items-center gap-4 border-b border-black/[0.07] bg-white px-4 sm:px-6">
    <div class="flex min-w-0 shrink-0 items-center gap-3">
      <NuxtLink to="/dashboard/scorecard" aria-label="Central de Indicadores">
        <img src="/brand/hub-logo.png" alt="Hub" class="h-9 w-auto max-w-[190px]" />
      </NuxtLink>
      <button class="btn small hidden sm:inline-flex" type="button" @click="router.back()">
        <ArrowLeft :size="15" /> Voltar
      </button>
    </div>

    <div class="ml-auto flex items-center gap-2">
      <NuxtLink v-if="store.isAdmin" to="/dashboard/administracao" class="btn small" title="Administração">
        <Shield :size="15" /> <span class="hidden sm:inline">Administração</span>
      </NuxtLink>
      <div class="relative">
        <button class="btn small" type="button" @click="menuOpen = !menuOpen">
          <UserRound :size="15" />
          <span class="hidden max-w-48 truncate sm:inline">{{ store.user?.name || "Usuário" }}</span>
          <span class="badge info">{{ store.user?.role }}</span>
        </button>
        <div v-if="menuOpen" class="absolute right-0 z-50 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <strong class="block truncate text-sm text-slate-700">{{ store.user?.name }}</strong>
          <span class="block truncate text-xs text-slate-500">{{ store.user?.email }}</span>
          <button class="btn danger mt-3 w-full small" type="button" @click="logout">
            <LogOut :size="14" /> Sair
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
