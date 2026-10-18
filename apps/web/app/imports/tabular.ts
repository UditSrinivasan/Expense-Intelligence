export type FinancialField =
  | "transaction_date"
  | "posting_date"
  | "description"
  | "amount"
  | "debit"
  | "credit"
  | "currency"
  | "reference"
  | "ignore";
export type ColumnMapping = Record<string, FinancialField>;
export type ParsedTable = {
  sheetNames: string[];
  sheetName: string;
  headers: string[];
  rows: string[][];
  headerRow: number;
  encoding?: string;
  delimiter?: string;
};
export type NormalizedCandidate = {
  source_row: number;
  transaction_date: string;
  posting_date?: string;
  description: string;
  direction: "expense" | "income" | "transfer";
  amount: string;
  currency: string;
  reference?: string;
  included: boolean;
  issues: string[];
};

export function parseCsvRows(text: string, delimiter: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [],
    cell = "",
    quoted = false;
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        cell += '"';
        index++;
      } else quoted = !quoted;
    } else if (character === delimiter && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && text[index + 1] === "\n") index++;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else cell += character;
  }
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  if (quoted) throw new Error("CSV contains an unterminated quoted field.");
  return rows;
}

export function buildParsedTable(
  rows: unknown[][],
  extra: Partial<ParsedTable>,
): ParsedTable {
  const maxRows = 10_000,
    maxColumns = 100,
    maxCell = 2_000;
  if (rows.length > maxRows + 25)
    throw new Error(
      `Files are limited to ${maxRows.toLocaleString()} data rows.`,
    );
  const strings = rows.map((row) =>
    row
      .slice(0, maxColumns + 1)
      .map((cell) => String(cell ?? "").slice(0, maxCell)),
  );
  if (strings.some((row) => row.length > maxColumns))
    throw new Error(`Sheets are limited to ${maxColumns} columns.`);
  const terms =
    /date|description|narration|details|amount|debit|credit|withdrawal|deposit|reference|currency/i;
  let headerRow = 0,
    score = -1;
  strings.slice(0, 25).forEach((row, index) => {
    const next =
      row.filter((cell) => terms.test(cell)).length * 3 +
      new Set(row.filter(Boolean)).size;
    if (next > score) {
      score = next;
      headerRow = index;
    }
  });
  const headers = strings[headerRow].map(
    (value, index) => value.trim() || `Column ${index + 1}`,
  );
  return {
    sheetNames: [],
    sheetName: "Statement",
    headers,
    rows: strings
      .slice(headerRow + 1)
      .filter((row) => row.some((cell) => cell.trim())),
    headerRow,
    ...extra,
  };
}

const aliases: Record<Exclude<FinancialField, "ignore">, string[]> = {
  transaction_date: ["date", "transaction date", "txn date", "value date"],
  posting_date: ["posting date", "posted date"],
  description: [
    "description",
    "narration",
    "details",
    "merchant",
    "transaction details",
    "memo",
  ],
  amount: ["amount", "transaction amount"],
  debit: ["debit", "withdrawal", "money out", "paid out"],
  credit: ["credit", "deposit", "money in", "paid in"],
  currency: ["currency", "ccy"],
  reference: ["reference", "ref", "transaction id", "utr", "payment reference"],
};

export function suggestMapping(headers: string[]): ColumnMapping {
  return Object.fromEntries(
    headers.map((header) => {
      const normalized = header.trim().toLowerCase().replace(/[_-]+/g, " ");
      const match = Object.entries(aliases).find(
        ([, values]) =>
          values.includes(normalized) ||
          values.some((value) => normalized.includes(value)),
      );
      return [header, (match?.[0] ?? "ignore") as FinancialField];
    }),
  );
}

function exactDecimal(
  value: string,
  convention: "dot" | "comma",
): string | undefined {
  let text = value.trim().replace(/[₹£$€\s]/g, "");
  if (!text) return undefined;
  const negative = /^\(.*\)$/.test(text);
  text = text.replace(/[()]/g, "");
  if (convention === "comma") text = text.replace(/\./g, "").replace(",", ".");
  else text = text.replace(/,/g, "");
  if (!/^[-+]?\d+(\.\d+)?$/.test(text)) return undefined;
  const unsigned = text.replace(/^[-+]/, "").replace(/^0+(?=\d)/, "");
  return `${negative || text.startsWith("-") ? "-" : ""}${unsigned || "0"}`;
}

function exactDate(
  value: string,
  order: "DMY" | "MDY" | "YMD",
  ambiguousDateConfirmed: boolean,
): { value?: string; ambiguous?: boolean } {
  const iso = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/.exec(value.trim());
  if (iso) return validDate(+iso[1], +iso[2], +iso[3]);
  const match = /^(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})$/.exec(value.trim());
  if (!match) return {};
  const first = +match[1],
    second = +match[2],
    year = match[3].length === 2 ? 2000 + +match[3] : +match[3];
  if (
    first <= 12 &&
    second <= 12 &&
    first !== second &&
    !ambiguousDateConfirmed
  )
    return { ambiguous: true };
  return order === "MDY"
    ? validDate(year, first, second)
    : validDate(year, second, first);
}

function validDate(year: number, month: number, day: number) {
  const candidate = new Date(Date.UTC(year, month - 1, day));
  return candidate.getUTCFullYear() === year &&
    candidate.getUTCMonth() === month - 1 &&
    candidate.getUTCDate() === day
    ? {
        value: `${year.toString().padStart(4, "0")}-${month.toString().padStart(2, "0")}-${day.toString().padStart(2, "0")}`,
      }
    : {};
}

export function normalizeRows(
  table: ParsedTable,
  mapping: ColumnMapping,
  options: {
    dateOrder: "DMY" | "MDY" | "YMD";
    ambiguousDateConfirmed: boolean;
    decimalConvention: "dot" | "comma";
    defaultCurrency: string;
  },
): NormalizedCandidate[] {
  const index = (field: FinancialField) =>
    table.headers.findIndex((header) => mapping[header] === field);
  const dateIndex = index("transaction_date"),
    descriptionIndex = index("description"),
    amountIndex = index("amount"),
    debitIndex = index("debit"),
    creditIndex = index("credit"),
    currencyIndex = index("currency"),
    referenceIndex = index("reference"),
    postingIndex = index("posting_date");
  if (
    dateIndex < 0 ||
    descriptionIndex < 0 ||
    (amountIndex < 0 && debitIndex < 0 && creditIndex < 0)
  )
    throw new Error(
      "Map a transaction date, description, and amount or debit/credit columns.",
    );
  return table.rows.map((row, rowIndex) => {
    const issues: string[] = [];
    const parsedDate = exactDate(
      row[dateIndex] ?? "",
      options.dateOrder,
      options.ambiguousDateConfirmed,
    );
    if (parsedDate.ambiguous)
      issues.push("Ambiguous date: choose DMY or MDY explicitly");
    else if (!parsedDate.value) issues.push("Invalid transaction date");
    const debit =
      debitIndex >= 0
        ? exactDecimal(row[debitIndex] ?? "", options.decimalConvention)
        : undefined;
    const credit =
      creditIndex >= 0
        ? exactDecimal(row[creditIndex] ?? "", options.decimalConvention)
        : undefined;
    const signed =
      amountIndex >= 0
        ? exactDecimal(row[amountIndex] ?? "", options.decimalConvention)
        : undefined;
    if (debit && credit) issues.push("Both debit and credit contain amounts");
    const direction =
      credit && !debit
        ? "income"
        : debit
          ? "expense"
          : signed?.startsWith("-")
            ? "expense"
            : "income";
    const amount = (debit ?? credit ?? signed ?? "").replace(/^-/, "");
    if (!amount || amount === "0") issues.push("Invalid or zero amount");
    const description = (row[descriptionIndex] ?? "").trim();
    if (!description) issues.push("Missing description");
    if (/^[=+@]/.test(description))
      issues.push("Formula-like description requires review");
    const posting =
      postingIndex >= 0 && row[postingIndex]
        ? exactDate(
            row[postingIndex],
            options.dateOrder,
            options.ambiguousDateConfirmed,
          )
        : {};
    return {
      source_row: table.headerRow + rowIndex + 2,
      transaction_date: parsedDate.value ?? "",
      ...(posting.value ? { posting_date: posting.value } : {}),
      description,
      direction,
      amount,
      currency: (currencyIndex >= 0
        ? row[currencyIndex]
        : options.defaultCurrency
      )
        .trim()
        .toUpperCase(),
      ...(referenceIndex >= 0 && row[referenceIndex]
        ? { reference: row[referenceIndex].trim() }
        : {}),
      included: issues.length === 0,
      issues,
    };
  });
}
