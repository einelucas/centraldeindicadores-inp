/**
 * Leitura de planilhas Excel/CSV no NAVEGADOR.
 * Migrado de readWorkbookFile()/readWorkbookMatrix() do HTML original.
 *
 * Os arquivos são processados no cliente; apenas JSON normalizado vai à API.
 */

import * as XLSX from "xlsx";

/** Lê a primeira aba como array de objetos (header = primeira linha). */
export async function readWorkbookFile(
  file: File,
): Promise<Array<Record<string, unknown>>> {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array", cellDates: true });
  const firstSheetName = wb.SheetNames[0];
  if (!firstSheetName) throw new Error("Planilha sem abas");
  const sheet = wb.Sheets[firstSheetName];
  if (!sheet) throw new Error("Aba inicial não encontrada");
  return XLSX.utils.sheet_to_json<Record<string, unknown>>(sheet, {
    defval: null,
    raw: true,
  });
}

/** Lê a primeira aba como matriz (array de arrays). Migrado de readWorkbookMatrix(). */
export async function readWorkbookMatrix(file: File): Promise<unknown[][]> {
  const buf = await file.arrayBuffer();
  const wb = XLSX.read(buf, { type: "array", cellDates: true });
  const firstSheetName = wb.SheetNames[0];
  if (!firstSheetName) throw new Error("Planilha sem abas");
  const sheet = wb.Sheets[firstSheetName];
  if (!sheet) throw new Error("Aba inicial não encontrada");
  return XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, defval: null });
}
