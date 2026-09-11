<script setup lang="ts">
import { RefreshCw } from "lucide-vue-next";
import type { ImportJob } from "~/types/api";
import { formatDate, formatNumber } from "~/utils/format";

const api = useApi();
const jobs = ref<ImportJob[]>([]);
const loading = ref(true);
const message = ref("");
const errorsOpen = ref(false);
const errors = ref<Array<Record<string, unknown>>>([]);
const selected = ref<ImportJob | null>(null);
const page = ref(1);
const pageSize = 20;

const totalPages = computed(() => Math.max(1, Math.ceil(jobs.value.length / pageSize)));
const pagedJobs = computed(() => jobs.value.slice((page.value - 1) * pageSize, page.value * pageSize));

function statusOk(status: string) {
  return status === "COMPLETED";
}

async function load() {
  loading.value = true;
  try {
    jobs.value = await api.get<ImportJob[]>("/importacoes");
    page.value = 1;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar importações.";
  } finally {
    loading.value = false;
  }
}

async function showErrors(job: ImportJob) {
  selected.value = job;
  try {
    errors.value = (await api.get<{ items: Array<Record<string, unknown>> }>(`/importacoes/${job.id}/erros`)).items;
    errorsOpen.value = true;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar erros.";
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-end">
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
            <TableHead>Início</TableHead>
            <TableHead>Módulo</TableHead>
            <TableHead>Arquivo</TableHead>
            <TableHead>Status</TableHead>
            <TableHead class="text-right">Encontrados</TableHead>
            <TableHead class="text-right">Inseridos</TableHead>
            <TableHead class="text-right">Atualizados</TableHead>
            <TableHead class="text-right">Ignorados</TableHead>
            <TableHead class="text-right">Rejeitados</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!pagedJobs.length">
            <TableCell colspan="9" class="py-8 text-center text-neutralbrand">
              Nenhuma importação registrada ainda.
            </TableCell>
          </TableRow>
          <TableRow v-for="job in pagedJobs" :key="job.id">
            <TableCell>{{ formatDate(job.startedAt, true) }}</TableCell>
            <TableCell>{{ job.module }}</TableCell>
            <TableCell>{{ job.fileName }}</TableCell>
            <TableCell><StatusBadge :ok="statusOk(job.status)">{{ job.status }}</StatusBadge></TableCell>
            <TableCell class="text-right">{{ formatNumber(job.totalFound) }}</TableCell>
            <TableCell class="text-right">{{ formatNumber(job.totalInserted) }}</TableCell>
            <TableCell class="text-right">{{ formatNumber(job.totalUpdated) }}</TableCell>
            <TableCell class="text-right">{{ formatNumber(job.totalIgnored) }}</TableCell>
            <TableCell class="text-right">
              <button
                v-if="job.totalRejected"
                type="button"
                class="font-semibold text-danger underline-offset-2 hover:underline"
                @click="showErrors(job)"
              >
                {{ job.totalRejected }}
              </button>
              <span v-else>0</span>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div v-if="totalPages > 1" class="flex items-center justify-between text-sm">
        <span class="text-neutralbrand">Página {{ page }} de {{ totalPages }} · {{ jobs.length }} importações</span>
        <div class="flex gap-2">
          <Button variant="outline" size="sm" :disabled="page <= 1" @click="page--">Anterior</Button>
          <Button variant="outline" size="sm" :disabled="page >= totalPages" @click="page++">Próxima</Button>
        </div>
      </div>
    </template>

    <Dialog :open="errorsOpen" @update:open="errorsOpen = $event">
      <DialogContent class="max-w-2xl">
        <DialogHeader>
          <div>
            <DialogTitle>Erros — {{ selected?.fileName }}</DialogTitle>
            <DialogDescription>Linhas rejeitadas nesta importação.</DialogDescription>
          </div>
          <DialogCloseButton @click="errorsOpen = false" />
        </DialogHeader>
        <div class="max-h-[60vh] overflow-auto p-5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Lote</TableHead>
                <TableHead>Linha</TableHead>
                <TableHead>Campo</TableHead>
                <TableHead>Mensagem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="(error, index) in errors" :key="index">
                <TableCell>{{ error.batchNumber ?? "—" }}</TableCell>
                <TableCell>{{ error.rowNumber ?? "—" }}</TableCell>
                <TableCell>{{ error.field ?? "—" }}</TableCell>
                <TableCell>{{ error.message }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
