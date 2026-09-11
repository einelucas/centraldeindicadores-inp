<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import { formatDate } from "~/utils/format";

interface Audit {
  id: string;
  action: string;
  entity: string;
  entityId: string | null;
  previousData: unknown;
  newData: unknown;
  metadata: unknown;
  createdAt: string;
  user: { name: string; email: string } | null;
}

const api = useApi();
const items = ref<Audit[]>([]);
const loading = ref(true);
const page = ref(1);
const pages = ref(1);
const entity = ref("");
const action = ref("");
const message = ref("");

async function load() {
  loading.value = true;
  try {
    const res = await api.get<{ items: Audit[]; pagination: { totalPages: number } }>("/auditoria", {
      page: page.value,
      pageSize: 50,
      entity: entity.value || undefined,
      action: action.value || undefined,
    });
    items.value = res.items;
    pages.value = res.pagination.totalPages;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar auditoria.";
  } finally {
    loading.value = false;
  }
}

watch([page, entity, action], load);
onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-end gap-3">
      <div class="space-y-1">
        <Label for="au-entity">Entidade</Label>
        <Input id="au-entity" v-model="entity" placeholder="ex.: User, ImportJob" @change="page = 1" />
      </div>
      <div class="space-y-1">
        <Label for="au-action">Ação</Label>
        <Input id="au-action" v-model="action" placeholder="ex.: scorecard.save" @change="page = 1" />
      </div>
      <Button variant="outline" size="icon" aria-label="Atualizar" @click="load">
        <RefreshCw class="size-4" />
      </Button>
    </div>

    <p v-if="message" class="text-sm text-danger">{{ message }}</p>
    <p v-else-if="loading" class="text-sm text-neutralbrand">Carregando…</p>

    <template v-else>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Quando</TableHead>
            <TableHead>Usuário</TableHead>
            <TableHead>Ação</TableHead>
            <TableHead>Entidade</TableHead>
            <TableHead>Registro</TableHead>
            <TableHead>Alteração</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!items.length">
            <TableCell colspan="6" class="py-8 text-center text-neutralbrand">
              Nenhum evento de auditoria encontrado.
            </TableCell>
          </TableRow>
          <TableRow v-for="item in items" :key="item.id">
            <TableCell>{{ formatDate(item.createdAt, true) }}</TableCell>
            <TableCell>{{ item.user?.name || item.user?.email || "sistema" }}</TableCell>
            <TableCell><Badge>{{ item.action }}</Badge></TableCell>
            <TableCell>{{ item.entity }}</TableCell>
            <TableCell>{{ item.entityId ?? "—" }}</TableCell>
            <TableCell>
              <details>
                <summary class="cursor-pointer text-sm text-primary">Visualizar</summary>
                <pre class="mt-1 max-w-xl overflow-auto text-xs">{{
                  JSON.stringify({ anterior: item.previousData, novo: item.newData, metadata: item.metadata }, null, 2)
                }}</pre>
              </details>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div v-if="pages > 1" class="flex items-center justify-between text-sm">
        <span class="text-neutralbrand">Página {{ page }} de {{ pages }}</span>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--">Anterior</Button>
          <Button variant="outline" size="sm" :disabled="page >= pages" @click="page++">Próxima</Button>
        </div>
      </div>
    </template>
  </div>
</template>
