type ImportModule = "rdo" | "idp" | "rnc" | "cinco-s";

export interface ParsedImportFile {
  fileName: string;
  count: number;
  error: string | null;
}

export interface ParsedImport {
  records: Array<Record<string, unknown>>;
  duplicates: number;
  errors: string[];
  perFile: ParsedImportFile[];
}

export function useImports() {
  const api = useApi();
  const config = useRuntimeConfig();

  async function parse(module: ImportModule, files: File[]): Promise<ParsedImport> {
    if (!files.length) return { records: [], duplicates: 0, errors: ["Selecione ao menos um arquivo."], perFile: [] };

    if (module === "rdo") {
      const { importRdoFiles } = await import("~/logic/features/rdo/importers/index");
      const result = await importRdoFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
        perFile: result.perFile.map(item => ({ fileName: item.fileName, count: item.count, error: item.error })),
      };
    }
    if (module === "rnc") {
      const { importRncFiles } = await import("~/logic/features/rnc/importers/index");
      const result = await importRncFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
        perFile: result.perFile.map(item => ({ fileName: item.fileName, count: item.count, error: item.error })),
      };
    }
    if (module === "cinco-s") {
      const { importFiveSFiles } = await import("~/logic/features/cinco-s/importers/index");
      const result = await importFiveSFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
        perFile: result.perFile.map(item => ({ fileName: item.fileName, count: item.records.length, error: item.error })),
      };
    }

    const { importIdpFiles } = await import("~/logic/features/idp/importers/index");
    const result = await importIdpFiles(files);
    return {
      records: result.records as unknown as Array<Record<string, unknown>>,
      duplicates: 0,
      errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
      perFile: result.perFile.map(item => ({ fileName: item.fileName, count: item.record ? 1 : 0, error: item.error })),
    };
  }

  async function send(
    module: ImportModule,
    fileName: string,
    records: Array<Record<string, unknown>>,
    onProgress?: (progress: { batch: number; totalBatches: number; totals: { inserted: number; updated: number; ignored: number; rejected: number } }) => void,
  ) {
    const first = records[0] ?? {};
    const start = await api.post<{ importJobId: string; status: string }>("/importacoes/iniciar", {
      module,
      fileName,
      referenceYear: typeof first.referenceYear === "number" ? first.referenceYear : null,
      referenceMonth: typeof first.referenceMonth === "number" ? first.referenceMonth : null,
      totalFound: records.length,
    });
    const batchSize = Math.max(1, Number(config.public.importBatchSize) || 500);
    const totalBatches = Math.max(1, Math.ceil(records.length / batchSize));
    const totals = { inserted: 0, updated: 0, ignored: 0, rejected: 0 };
    for (let offset = 0; offset < records.length; offset += batchSize) {
      const batchNumber = Math.floor(offset / batchSize) + 1;
      const outcome = await api.post<typeof totals & { errors: Array<{ message: string }> }>(
        `/importacoes/${start.importJobId}/lotes`,
        { batchNumber, records: records.slice(offset, offset + batchSize) },
      );
      totals.inserted += outcome.inserted;
      totals.updated += outcome.updated;
      totals.ignored += outcome.ignored;
      totals.rejected += outcome.rejected;
      onProgress?.({ batch: batchNumber, totalBatches, totals: { ...totals } });
    }
    const finish = await api.post<{ status: string; totals: { found: number; inserted: number; updated: number; ignored: number; rejected: number } }>(
      `/importacoes/${start.importJobId}/finalizar`,
    );
    return { importJobId: start.importJobId, ...finish };
  }

  return { parse, send };
}
