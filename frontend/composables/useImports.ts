type ImportModule = "rdo" | "idp" | "rnc" | "cinco-s";

export interface ParsedImport {
  records: Array<Record<string, unknown>>;
  duplicates: number;
  errors: string[];
}

export function useImports() {
  const api = useApi();
  const config = useRuntimeConfig();

  async function parse(module: ImportModule, files: File[]): Promise<ParsedImport> {
    if (!files.length) return { records: [], duplicates: 0, errors: ["Selecione ao menos um arquivo."] };

    if (module === "rdo") {
      const { importRdoFiles } = await import("../../src/features/rdo/importers/index");
      const result = await importRdoFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
      };
    }
    if (module === "rnc") {
      const { importRncFiles } = await import("../../src/features/rnc/importers/index");
      const result = await importRncFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
      };
    }
    if (module === "cinco-s") {
      const { importFiveSFiles } = await import("../../src/features/cinco-s/importers/index");
      const result = await importFiveSFiles(files);
      return {
        records: result.records as unknown as Array<Record<string, unknown>>,
        duplicates: result.duplicates,
        errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
      };
    }

    const { importIdpFiles } = await import("../../src/features/idp/importers/index");
    const result = await importIdpFiles(files);
    return {
      records: result.records as unknown as Array<Record<string, unknown>>,
      duplicates: 0,
      errors: result.perFile.flatMap(item => item.error ? [`${item.fileName}: ${item.error}`] : []),
    };
  }

  async function send(module: ImportModule, fileName: string, records: Array<Record<string, unknown>>) {
    const first = records[0] ?? {};
    const start = await api.post<{ importJobId: string; status: string }>("/importacoes/iniciar", {
      module,
      fileName,
      referenceYear: typeof first.referenceYear === "number" ? first.referenceYear : null,
      referenceMonth: typeof first.referenceMonth === "number" ? first.referenceMonth : null,
      totalFound: records.length,
    });
    const batchSize = Math.max(1, Number(config.public.importBatchSize) || 500);
    const totals = { inserted: 0, updated: 0, ignored: 0, rejected: 0 };
    for (let offset = 0; offset < records.length; offset += batchSize) {
      const outcome = await api.post<typeof totals & { errors: Array<{ message: string }> }>(
        `/importacoes/${start.importJobId}/lotes`,
        { batchNumber: Math.floor(offset / batchSize) + 1, records: records.slice(offset, offset + batchSize) },
      );
      totals.inserted += outcome.inserted;
      totals.updated += outcome.updated;
      totals.ignored += outcome.ignored;
      totals.rejected += outcome.rejected;
    }
    const finish = await api.post<{ status: string; totals: { found: number; inserted: number; updated: number; ignored: number; rejected: number } }>(
      `/importacoes/${start.importJobId}/finalizar`,
    );
    return { importJobId: start.importJobId, ...finish };
  }

  return { parse, send };
}
