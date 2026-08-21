import { utils, writeFile } from "xlsx";
import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";

export function useExport() {
  function excel(fileName: string, rows: Array<Record<string, unknown>>) {
    const book = utils.book_new();
    const sheet = utils.json_to_sheet(rows.length ? rows : [{ mensagem: "Sem dados" }]);
    utils.book_append_sheet(book, sheet, "Dados");
    writeFile(book, fileName.endsWith(".xlsx") ? fileName : `${fileName}.xlsx`);
  }

  function pdf(fileName: string, title: string, rows: Array<Record<string, unknown>>) {
    const document = new jsPDF({ orientation: rows.length && Object.keys(rows[0]!).length > 6 ? "landscape" : "portrait" });
    document.setFontSize(16);
    document.setTextColor(33, 55, 88);
    document.text(title, 14, 16);
    const columns = rows.length ? Object.keys(rows[0]!) : ["mensagem"];
    const body = rows.length ? rows.map(row => columns.map(column => String(row[column] ?? "—"))) : [["Sem dados"]];
    autoTable(document, { head: [columns], body, startY: 23, styles: { fontSize: 7 }, headStyles: { fillColor: [48, 79, 126] } });
    document.save(fileName.endsWith(".pdf") ? fileName : `${fileName}.pdf`);
  }

  return { excel, pdf };
}
