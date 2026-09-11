<script setup lang="ts">
import { Plus, RefreshCw } from "lucide-vue-next";
import type { Role } from "~/types/api";
import { formatDate } from "~/utils/format";

interface UserRow {
  id: string;
  name: string;
  email: string;
  role: Role;
  active: boolean;
  authProvider: string;
  lastLoginAt: string | null;
  createdAt: string;
}

const ROLES: Role[] = ["VIEWER", "ANALYST", "ADMIN"];

const api = useApi();
const users = ref<UserRow[]>([]);
const loading = ref(true);
const busy = ref(false);
const message = ref("");
const form = reactive<{ name: string; email: string; role: Role }>({ name: "", email: "", role: "VIEWER" });

async function load() {
  loading.value = true;
  try {
    users.value = (await api.get<{ items: UserRow[] }>("/usuarios")).items;
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao carregar usuários.";
  } finally {
    loading.value = false;
  }
}

async function create() {
  busy.value = true;
  try {
    await api.post("/usuarios", form);
    Object.assign(form, { name: "", email: "", role: "VIEWER" });
    message.value = "Usuário criado.";
    await load();
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao criar usuário.";
  } finally {
    busy.value = false;
  }
}

async function update(user: UserRow, body: Record<string, unknown>) {
  busy.value = true;
  try {
    await api.patch(`/usuarios/${user.id}`, body);
    await load();
  } catch (cause) {
    message.value = cause instanceof Error ? cause.message : "Erro ao atualizar usuário.";
  } finally {
    busy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="space-y-6">
    <Card>
      <CardHeader>
        <CardTitle>Novo usuário</CardTitle>
        <CardDescription>O vínculo OIDC poderá ser concluído no primeiro acesso corporativo.</CardDescription>
      </CardHeader>
      <CardContent>
        <form class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" @submit.prevent="create">
          <div class="space-y-1">
            <Label for="um-name">Nome</Label>
            <Input id="um-name" v-model="form.name" required />
          </div>
          <div class="space-y-1">
            <Label for="um-email">E-mail</Label>
            <Input id="um-email" v-model="form.email" type="email" required />
          </div>
          <div class="space-y-1">
            <Label for="um-role">Perfil</Label>
            <Select id="um-role" v-model="form.role">
              <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
            </Select>
          </div>
          <div class="flex items-end">
            <Button type="submit" :disabled="busy || !form.name || !form.email" class="w-full">
              <Plus class="size-4" /> Criar usuário
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>

    <div class="flex items-center justify-between">
      <p v-if="message" class="text-sm text-neutralbrand">{{ message }}</p>
      <div class="ml-auto" />
      <Button variant="outline" size="icon" aria-label="Atualizar" @click="load">
        <RefreshCw class="size-4" />
      </Button>
    </div>

    <p v-if="loading" class="text-sm text-neutralbrand">Carregando…</p>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>Nome</TableHead>
          <TableHead>E-mail</TableHead>
          <TableHead>Perfil</TableHead>
          <TableHead>Provedor</TableHead>
          <TableHead>Último acesso</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-if="!users.length">
          <TableCell colspan="6" class="py-8 text-center text-neutralbrand">Nenhum usuário cadastrado.</TableCell>
        </TableRow>
        <TableRow v-for="user in users" :key="user.id">
          <TableCell>
            <Input
              :model-value="user.name"
              @change="update(user, { name: ($event.target as HTMLInputElement).value })"
            />
          </TableCell>
          <TableCell>{{ user.email }}</TableCell>
          <TableCell>
            <Select :model-value="user.role" @change="update(user, { role: ($event.target as HTMLSelectElement).value })">
              <option v-for="r in ROLES" :key="r" :value="r">{{ r }}</option>
            </Select>
          </TableCell>
          <TableCell><Badge variant="secondary">{{ user.authProvider }}</Badge></TableCell>
          <TableCell>{{ formatDate(user.lastLoginAt, true) }}</TableCell>
          <TableCell>
            <button :disabled="busy" title="Clique para alternar" @click="update(user, { active: !user.active })">
              <StatusBadge :ok="user.active">{{ user.active ? "Ativo" : "Inativo" }}</StatusBadge>
            </button>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
</template>
