<script setup lang="ts">
import type { Role } from "~/types/api";
definePageMeta({ publicLayout: true });
const { store, login, devAuthEnabled }=useAuth();const loading=ref(false),error=ref("");
if (store.token && await store.loadUser()) await navigateTo("/dashboard/scorecard");
async function oidc(){loading.value=true;error.value="";try{await login();}catch(cause){error.value=cause instanceof Error?cause.message:"Não foi possível iniciar o login.";}finally{loading.value=false;}}
async function dev(role:Role){loading.value=true;error.value="";try{await store.loginDev(role);await navigateTo("/dashboard/scorecard");}catch(cause){error.value=cause instanceof Error?cause.message:"Falha na autenticação de desenvolvimento.";}finally{loading.value=false;}}
</script>
<template><div class="login-page"><img src="/brand/usina.jpg" alt="" class="login-background"/><section class="login-card"><img src="/brand/logo-inpasa.png" alt="Inpasa" class="login-logo"/><h1>Central de Indicadores</h1><p>Acesse com sua conta corporativa.</p><button class="btn primary login-submit" :disabled="loading" @click="oidc">{{loading?'Aguarde…':'Entrar com conta corporativa'}}</button><template v-if="devAuthEnabled"><div class="my-4 flex items-center gap-3 text-xs text-slate-400"><span class="h-px flex-1 bg-slate-200"/>Desenvolvimento<span class="h-px flex-1 bg-slate-200"/></div><div class="grid grid-cols-3 gap-2"><button class="btn small" :disabled="loading" @click="dev('VIEWER')">Viewer</button><button class="btn small" :disabled="loading" @click="dev('ANALYST')">Analyst</button><button class="btn small" :disabled="loading" @click="dev('ADMIN')">Admin</button></div></template><p v-if="error" class="login-error">{{error}}</p></section></div></template>
