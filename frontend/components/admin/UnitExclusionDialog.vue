<script setup lang="ts">
import { Ban, Loader2 } from "lucide-vue-next";

export interface UnitExclusionOption {
  code: string;
  label: string;
}

const props = withDefaults(
  defineProps<{
    open: boolean;
    units: UnitExclusionOption[];
    excluded: readonly string[];
    busy?: boolean;
    title?: string;
    description?: string;
  }>(),
  {
    busy: false,
    title: "Ignorar unidades",
    description: "Unidades marcadas continuam visíveis nas tabelas, mas ficam de fora dos cálculos consolidados e do painel publicado.",
  },
);
const emit = defineEmits<{ "update:open": [value: boolean]; save: [next: string[]] }>();

const selected = ref<Set<string>>(new Set(props.excluded));

watch(
  () => props.open,
  (open) => {
    if (open) selected.value = new Set(props.excluded);
  },
);

function toggle(code: string) {
  const next = new Set(selected.value);
  if (next.has(code)) next.delete(code);
  else next.add(code);
  selected.value = next;
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="flex flex-col">
      <DialogHeader>
        <div>
          <DialogTitle>{{ title }}</DialogTitle>
          <DialogDescription>{{ description }}</DialogDescription>
        </div>
        <DialogCloseButton @click="emit('update:open', false)" />
      </DialogHeader>

      <div class="flex max-h-80 flex-col gap-1 overflow-y-auto p-4">
        <label
          v-for="unit in units"
          :key="unit.code"
          class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          <Checkbox :model-value="selected.has(unit.code)" @update:model-value="toggle(unit.code)" />
          {{ unit.label }}
        </label>
        <p v-if="!units.length" class="px-2.5 py-2 text-sm text-muted-foreground">Nenhuma unidade reconhecida ainda.</p>
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" :disabled="busy" @click="emit('update:open', false)">Cancelar</Button>
        <Button type="button" :disabled="busy" @click="emit('save', Array.from(selected))">
          <Loader2 v-if="busy" class="size-3.5 animate-spin" />
          <Ban v-else class="size-3.5" />
          Salvar
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
