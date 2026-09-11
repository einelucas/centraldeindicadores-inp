import type { UploadImportResult } from "~/types/api";

export type ImportModule = "rdo" | "idp" | "rnc" | "cinco-s";

/**
 * Cliente de upload puro — o Nuxt não lê, interpreta nem normaliza nenhum
 * arquivo. Envia os arquivos originais por `multipart/form-data` para
 * `POST /importacoes/{modulo}/arquivos`; todo o parsing/validação/
 * normalização/dedup/persistência acontece no FastAPI numa única chamada.
 */
export function useFileUpload() {
  const api = useApi();

  async function uploadFiles(module: ImportModule, files: File[]): Promise<UploadImportResult> {
    const formData = new FormData();
    for (const file of files) formData.append("files", file);

    // Gerado por tentativa de envio (não por arquivo) — reenviar os mesmos
    // arquivos após uma falha de rede usa a MESMA chave, então o FastAPI
    // devolve o resultado já processado em vez de duplicar a importação.
    const idempotencyKey = crypto.randomUUID();

    return api.request<UploadImportResult>(`/importacoes/${module}/arquivos`, {
      method: "POST",
      body: formData,
      headers: { "Idempotency-Key": idempotencyKey },
    });
  }

  return { uploadFiles };
}
