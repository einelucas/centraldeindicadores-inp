import html2canvas from "html2canvas";
import { jsPDF } from "jspdf";
import type { Ref } from "vue";

/**
 * Exporta o painel inteiro (cards + gráficos) como imagem, dentro de um PDF —
 * porte de `src/lib/exports/panel-screenshot-pdf.ts` (repositório de
 * referência). Diferente de `useExport().pdf()`, que monta uma tabela de
 * dados — aqui o PDF é literalmente um retrato visual do painel publicado.
 */
export function usePanelPdfExport(target: Ref<HTMLElement | null>) {
  const exporting = ref(false);
  const error = ref<string | null>(null);

  async function exportPdf(fileName: string) {
    if (!target.value) return;
    exporting.value = true;
    error.value = null;
    try {
      const canvas = await html2canvas(target.value, {
        backgroundColor: "#f4f5f7",
        scale: Math.min(2, window.devicePixelRatio || 1.5),
        useCORS: true,
      });
      const image = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: canvas.width > canvas.height ? "landscape" : "portrait",
        unit: "px",
        format: [canvas.width, canvas.height],
      });
      pdf.addImage(image, "PNG", 0, 0, canvas.width, canvas.height);
      pdf.save(fileName);
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "Falha ao exportar o PDF.";
    } finally {
      exporting.value = false;
    }
  }

  return { exporting, error, exportPdf };
}
