import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import type { RncResult } from "~/logic/features/rnc/types";
import { formatRncUnitLabel } from "~/logic/features/rnc/utils/units";

const percent = (value: number) => `${Math.round(value * 100)}%`;
const days = (value: number | null) => value === null ? "—" : String(Math.round(value));

export function exportRncPdf(result: RncResult): void {
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(16);
  pdf.setTextColor(48, 79, 126);
  pdf.text("RNC — Não Conformidades", 40, 44);
  pdf.setFont("helvetica", "normal");
  pdf.setFontSize(9);
  pdf.setTextColor(110, 110, 110);
  pdf.text(`Gerado em ${new Date().toLocaleDateString("pt-BR")} · meta: ≤ ${result.metaDias} dias`, 40, 60);

  const cards = [
    ["RNC'S CRIADAS", result.totalCriadas.toLocaleString("pt-BR")],
    ["RNC'S TRATADAS", result.totalTratadas.toLocaleString("pt-BR")],
    ["ADERÊNCIA", percent(result.aderenciaTotal)],
    ["RESULTADO", result.resultadoDias === null ? "—" : `${days(result.resultadoDias)} dias`],
  ];
  const cardY = 78;
  const gap = 10;
  const cardWidth = (515 - gap * 3) / 4;
  cards.forEach(([label, value], index) => {
    const x = 40 + index * (cardWidth + gap);
    pdf.setDrawColor(228, 230, 234);
    pdf.roundedRect(x, cardY, cardWidth, 50, 5, 5);
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(7);
    pdf.setTextColor(107, 114, 128);
    pdf.text(label ?? "", x + 9, cardY + 17);
    pdf.setFontSize(13);
    pdf.setTextColor(index >= 2 ? 234 : 33, index >= 2 ? 162 : 55, index >= 2 ? 57 : 88);
    pdf.text(value ?? "", x + 9, cardY + 36);
  });

  autoTable(pdf, {
    startY: 146,
    head: [["Mês", "RNC Elaboradas", "RNC Tratadas", "Dias de resolução", "Situação"]],
    body: result.months.map((month) => [
      month.label,
      month.chamados,
      month.solucionados,
      days(month.diasMedios),
      month.diasMedios === null ? "Sem tratativa" : month.dentroMeta ? "Dentro da meta" : "Fora da meta",
    ]),
    headStyles: { fillColor: [48, 79, 126], textColor: 255 },
    styles: { font: "helvetica", fontSize: 8.5, cellPadding: 4 },
    theme: "grid",
  });

  const firstY = (pdf as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? 350;
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.setTextColor(48, 79, 126);
  pdf.text("Aderência por unidade", 40, firstY + 22);
  autoTable(pdf, {
    startY: firstY + 30,
    head: [["Unidade", "Criadas", "Tratadas", "Aderência"]],
    body: result.units.map((unit) => [formatRncUnitLabel(unit.name), unit.criadas, unit.tratadas, percent(unit.aderencia)]),
    headStyles: { fillColor: [48, 79, 126], textColor: 255 },
    styles: { font: "helvetica", fontSize: 8.5, cellPadding: 4 },
    theme: "grid",
  });

  const secondY = (pdf as jsPDF & { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? 520;
  pdf.setFont("helvetica", "bold");
  pdf.setFontSize(11);
  pdf.setTextColor(48, 79, 126);
  pdf.text("Ofensores", 40, secondY + 22);
  autoTable(pdf, {
    startY: secondY + 30,
    head: [["Ofensor", "Quantidade", "%"]],
    body: result.ofensores.map((item) => [item.name, item.count, percent(item.pct)]),
    headStyles: { fillColor: [48, 79, 126], textColor: 255 },
    styles: { font: "helvetica", fontSize: 8.5, cellPadding: 4 },
    theme: "grid",
  });
  pdf.save(`RNC_${new Date().toISOString().slice(0, 10)}.pdf`);
}
