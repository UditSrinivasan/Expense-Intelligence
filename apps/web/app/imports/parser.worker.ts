import readXlsxFile, { readSheetNames } from "read-excel-file/web-worker";
import { buildParsedTable, parseCsvRows, type ParsedTable } from "./tabular";

const MAX_BYTES = 10 * 1024 * 1024;

self.onmessage = async (
  event: MessageEvent<{ file: File; sheetName?: string }>,
) => {
  try {
    const { file, sheetName } = event.data;
    if (file.size > MAX_BYTES) throw new Error("Files are limited to 10 MiB.");
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!["csv", "xlsx"].includes(extension ?? ""))
      throw new Error("Choose a CSV or XLSX file.");
    if (extension === "xlsx") {
      const signature = new Uint8Array(await file.slice(0, 4).arrayBuffer());
      if (signature[0] !== 0x50 || signature[1] !== 0x4b)
        throw new Error("The XLSX signature does not match a ZIP workbook.");
      const sheetNames = await readSheetNames(file);
      if (sheetNames.length > 25)
        throw new Error("Workbooks are limited to 25 sheets.");
      const selected =
        sheetName && sheetNames.includes(sheetName) ? sheetName : sheetNames[0];
      const rows = await readXlsxFile(file, { sheet: selected });
      postMessage(buildParsedTable(rows, { sheetNames, sheetName: selected }));
    } else {
      const bytes = await file.arrayBuffer();
      let encoding = "utf-8",
        text: string;
      try {
        text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      } catch {
        encoding = "windows-1252";
        text = new TextDecoder(encoding).decode(bytes);
      }
      const delimiters = [",", ";", "\t", "|"];
      const delimiter = delimiters
        .map(
          (value) =>
            [
              value,
              text.slice(0, 10_000).split(value).length - 1,
            ] as const,
        )
        .sort((a, b) => b[1] - a[1])[0][0];
      postMessage(
        buildParsedTable(parseCsvRows(text.replace(/^\uFEFF/, ""), delimiter), {
          encoding,
          delimiter,
          sheetName: "CSV",
        }),
      );
    }
  } catch (error) {
    postMessage({
      error:
        error instanceof Error
          ? error.message
          : "The file could not be parsed safely.",
    });
  }
};
