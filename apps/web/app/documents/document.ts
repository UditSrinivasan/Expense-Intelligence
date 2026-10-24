export type Evidence = {
  page: number;
  text: string;
  confidence: number;
};

export type ReceiptItem = {
  label: string;
  quantity: string;
  unit_price: string;
  line_total: string;
  category_id?: string;
  evidence?: Evidence;
};

export type ReceiptCandidate = {
  merchant: string;
  document_date: string;
  currency: string;
  items: ReceiptItem[];
  discount: string;
  tax: string;
  service_charge: string;
  delivery_fee: string;
  packaging_fee: string;
  tip: string;
  rounding: string;
  total: string;
  confidence: number;
  issues: string[];
};

export type DocumentExtraction = {
  document_type: "bank_statement" | "receipt" | "itemized_bill" | "other";
  source_format: "pdf" | "jpg" | "png" | "webp";
  pages: number;
  used_ocr: boolean;
  elapsed_ms: number;
  text: string;
  transactions: DocumentTransaction[];
  receipt: ReceiptCandidate;
};

export type DocumentTransaction = {
  source_row: number;
  transaction_date: string;
  description: string;
  direction: "expense" | "income";
  amount: string;
  currency: string;
  included: boolean;
  issues: string[];
  source_page: number;
};

const moneyPattern = /(?:₹|£|\$|€|INR|GBP|USD|EUR)?\s*(-?\d[\d,]*\.\d{2})\s*$/i;

function detectCurrency(text: string): "INR" | "GBP" | "USD" | "EUR" {
  if (/₹|\bINR\b/i.test(text)) return "INR";
  if (/£|\bGBP\b/i.test(text)) return "GBP";
  if (/€|\bEUR\b/i.test(text)) return "EUR";
  if (/\$|\bUSD\b/i.test(text)) return "USD";
  return "INR";
}

export function addMoney(values: string[]): string {
  const units = values.reduce((sum, value) => {
    const negative = value.startsWith("-");
    const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
    const minor =
      BigInt(whole || "0") * 100n + BigInt(fraction.padEnd(2, "0").slice(0, 2));
    return sum + (negative ? -minor : minor);
  }, 0n);
  const sign = units < 0 ? "-" : "";
  const absolute = units < 0 ? -units : units;
  return `${sign}${absolute / 100n}.${(absolute % 100n).toString().padStart(2, "0")}`;
}

function amount(line: string): string | undefined {
  const match = moneyPattern.exec(line.trim());
  return match?.[1].replace(/,/g, "");
}

export function extractReceipt(text: string): ReceiptCandidate {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => Boolean(line) && !/^\[\[PAGE \d+\]\]$/.test(line))
    .slice(0, 500);
  const currency = detectCurrency(text);
  const dateMatch = text.match(
    /\b(\d{4})[-/](\d{2})[-/](\d{2})\b|\b(\d{2})[/-](\d{2})[/-](\d{4})\b/,
  );
  const document_date = dateMatch
    ? dateMatch[1]
      ? `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`
      : `${dateMatch[6]}-${dateMatch[5]}-${dateMatch[4]}`
    : "";
  const special: Record<string, string> = {
    discount: "0.00",
    tax: "0.00",
    service_charge: "0.00",
    delivery_fee: "0.00",
    packaging_fee: "0.00",
    tip: "0.00",
    rounding: "0.00",
    total: "",
  };
  const items: ReceiptItem[] = [];
  for (const [index, line] of lines.entries()) {
    const value = amount(line);
    if (!value) continue;
    const lower = line.toLowerCase();
    const key =
      lower.includes("grand total") || /^total\b/i.test(line)
        ? "total"
        : /gst|vat|tax/.test(lower)
          ? "tax"
          : /delivery/.test(lower)
            ? "delivery_fee"
            : /packag/.test(lower)
              ? "packaging_fee"
          : /service\s*charge/.test(lower)
            ? "service_charge"
            : /tip|gratuity/.test(lower)
              ? "tip"
              : /round/.test(lower)
                ? "rounding"
                : /discount|saving/.test(lower)
                  ? "discount"
                  : undefined;
    if (key) {
      const normalized =
        key === "tax" && /included/i.test(line)
          ? "0.00"
          : key === "discount" && !value.startsWith("-")
            ? `-${value}`
            : value;
      special[key] = key === "total" ? normalized : addMoney([special[key], normalized]);
    } else {
      const label = line
        .slice(0, line.lastIndexOf(value.replace(/,/g, "")))
        .replace(/[₹£$€]/g, "")
        .replace(/\b(?:INR|GBP|USD|EUR)\b/gi, "")
        .trim();
      if (label)
        items.push({
          label,
          quantity: "1",
          unit_price: value,
          line_total: value,
          evidence: { page: 1, text: line, confidence: 0.7 },
        });
    }
  }
  const calculated = addMoney([
    ...items.map((item) => item.line_total),
    special.discount,
    special.tax,
    special.service_charge,
    special.delivery_fee,
    special.packaging_fee,
    special.tip,
    special.rounding,
  ]);
  const issues: string[] = [];
  if (!document_date) issues.push("Confirm the document date");
  if (!special.total) issues.push("Confirm the final total");
  if (special.total && calculated !== Number(special.total).toFixed(2))
    issues.push(`Components reconcile to ${calculated}, not ${special.total}`);
  return {
    merchant:
      lines
        .find((line) => !moneyPattern.test(line) && line.length > 2)
        ?.slice(0, 160) ?? "",
    document_date,
    currency,
    items: items.slice(0, 100),
    ...special,
    confidence: items.length && special.total ? 0.7 : 0.35,
    issues,
  } as ReceiptCandidate;
}

export function extractStatement(text: string): DocumentTransaction[] {
  const currency = detectCurrency(text);
  let sourcePage = 1;
  return text
    .split(/\r?\n/)
    .flatMap((line, index) => {
      const page = /^\[\[PAGE (\d+)\]\]$/.exec(line.trim());
      if (page) {
        sourcePage = Number(page[1]);
        return [];
      }
      const dateMatch = line.match(/\b(\d{2})[/-](\d{2})[/-](\d{4})\b/);
      const value = amount(line);
      if (!dateMatch || !value) return [];
      const description = line
        .replace(dateMatch[0], "")
        .replace(moneyPattern, "")
        .trim();
      const direction =
        /\b(cr|credit|deposit|refund)\b/i.test(line) || value.startsWith("-")
          ? "income"
          : "expense";
      return [
        {
          source_row: index + 1,
          transaction_date: `${dateMatch[3]}-${dateMatch[2]}-${dateMatch[1]}`,
          description: description || "Unclear statement entry",
          direction,
          amount: value.replace(/^-/, ""),
          currency,
          included: true,
          issues: description ? [] : ["Confirm description"],
          source_page: sourcePage,
        } satisfies DocumentTransaction,
      ];
    })
    .slice(0, 10_000);
}
