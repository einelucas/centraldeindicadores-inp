/** Porte de src/lib/batching/index.ts (repositório de referência). */

export const DEFAULT_IMPORT_BATCH_SIZE = 500;

export function chunk<T>(items: readonly T[], size: number = DEFAULT_IMPORT_BATCH_SIZE): T[][] {
  if (size <= 0) throw new Error("Tamanho de lote deve ser maior que zero");
  const batches: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    batches.push(items.slice(i, i + size));
  }
  return batches;
}
