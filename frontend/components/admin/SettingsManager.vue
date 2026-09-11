<script setup lang="ts">
import { RefreshCw, Save } from "lucide-vue-next";

interface Setting {
  key: string;
  value: unknown;
  updatedAt: string;
  draft: string;
}

/** Rótulos amigáveis para as chaves conhecidas — porte de
 * src/features/admin/components/SettingsManager.tsx (menos
 * `taxa-acidentes.target`, indicador removido). */
const LABELS: Record<string, string> = {
  "rdo.target": "RDO — meta de aprovação (fração)",
  "idp.target": "IDP/Cronograma — meta (fração)",
  "idp.excludedDisciplines": "IDP — disciplinas excluídas",
  "idp.excludedUnits": "IDP — unidades excluídas",
  "rnc.maxPrazoDias": "RNC — prazo máximo (dias)",
  "fiveS.target": "5S — meta (fração)",
  "fiveS.excludedUnits": "5S — unidades excluídas",
};

const api = useApi();
const items = ref<Setting[]>([]);
const loading = ref(true);
const busy = ref(false);
const message = ref("");

function serialize(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
function parse(value: string) {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

async function load() {
  loading.value = true;
  try {
    items.value = (await api.get<{ items: Array<Omit<Setting, "draft">> }>("/configuracoes")).items.map((item) => ({
      ...item,
      draft: serialize(item.value),
    }));
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar configurações.";
  } finally {
    loading.value = false;
  }
}

async function save(item: Setting) {
  busy.value = true;
  message.value = "";
  try {
    await api.patch("/configuracoes", { key: item.key, value: parse(item.draft) });
    message.value = `"${item.key}" salvo.`;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : `Falha ao salvar "${item.key}".`;
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p v-if="message" class="text-sm text-neutralbrand">{{ message }}</p>
      <div class="ml-auto" />
      <Button variant="outline" size="icon" aria-label="Atualizar" @click="load">
        <RefreshCw class="size-4" />
      </Button>
    </div>

    <p v-if="loading" class="text-sm text-neutralbrand">Carregando…</p>
    <div v-else class="space-y-3">
      <Card v-for="item in items" :key="item.key">
        <CardContent class="space-y-2 pt-5">
          <div class="flex items-baseline justify-between gap-2">
            <Label :for="`set-${item.key}`" class="normal-case tracking-normal text-sm font-semibold text-brand-dark">
              {{ LABELS[item.key] ?? item.key }}
            </Label>
            <code class="text-xs text-neutralbrand">{{ item.key }}</code>
          </div>
          <div class="flex gap-2">
            <Textarea :id="`set-${item.key}`" v-model="item.draft" class="min-h-9 flex-1 font-mono" />
            <Button :disabled="busy" @click="save(item)"><Save class="size-4" /> Salvar</Button>
          </div>
        </CardContent>
      </Card>
    </div>

    <p class="text-xs text-neutralbrand">
      Valores são interpretados como JSON quando possível (ex.: <code>0.80</code>,
      <code>["SP","CSC"]</code>); caso contrário, como texto. Metas em fração (0.80 = 80%).
    </p>
  </div>
</template>
