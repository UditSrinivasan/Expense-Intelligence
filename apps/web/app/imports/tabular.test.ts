import assert from "node:assert/strict";
import test from "node:test";
import {
  buildParsedTable,
  normalizeRows,
  parseCsvRows,
  suggestMapping,
} from "./tabular.ts";

test("parses quoted semicolon CSV and detects a header after preamble rows", () => {
  const rows = parseCsvRows(
    'Statement export\r\nDate;Narration;Debit;Credit\r\n02/01/2026;"Cafe; London";12,34;\r\n',
    ";",
  );
  const table = buildParsedTable(rows, { sheetName: "CSV" });
  assert.equal(table.headerRow, 1);
  assert.deepEqual(table.headers, ["Date", "Narration", "Debit", "Credit"]);
  assert.equal(table.rows[0][1], "Cafe; London");
});

test("normalizes debit and credit with exact decimal text", () => {
  const table = buildParsedTable(
    [
      ["Date", "Description", "Debit", "Credit", "Currency"],
      ["13/02/2026", "UPI SHOP", "12345678901234567890.12", "", "INR"],
      ["14/02/2026", "Salary", "", "42.10", "GBP"],
    ],
    { sheetName: "Transactions" },
  );
  const candidates = normalizeRows(table, suggestMapping(table.headers), {
    dateOrder: "DMY",
    ambiguousDateConfirmed: true,
    decimalConvention: "dot",
    defaultCurrency: "INR",
  });
  assert.equal(candidates[0].amount, "12345678901234567890.12");
  assert.equal(candidates[0].direction, "expense");
  assert.equal(candidates[1].direction, "income");
  assert.equal(candidates[1].currency, "GBP");
});

test("blocks ambiguous dates until the chosen interpretation is confirmed", () => {
  const table = buildParsedTable(
    [
      ["Date", "Description", "Amount"],
      ["01/02/2026", "Direct Debit", "10.00"],
    ],
    { sheetName: "CSV" },
  );
  const mapping = suggestMapping(table.headers);
  const blocked = normalizeRows(table, mapping, {
    dateOrder: "DMY",
    ambiguousDateConfirmed: false,
    decimalConvention: "dot",
    defaultCurrency: "GBP",
  });
  assert.match(blocked[0].issues.join(" "), /Ambiguous date/);
  const confirmed = normalizeRows(table, mapping, {
    dateOrder: "DMY",
    ambiguousDateConfirmed: true,
    decimalConvention: "dot",
    defaultCurrency: "GBP",
  });
  assert.equal(confirmed[0].transaction_date, "2026-02-01");
});

test("flags formula-like descriptions and rejects malformed quoted CSV", () => {
  assert.throws(() =>
    parseCsvRows('Date,Description\n01/01/2026,"broken', ","),
  );
  const table = buildParsedTable(
    [
      ["Date", "Description", "Amount"],
      ["2026-02-13", '=HYPERLINK("https://example.test")', "1.00"],
    ],
    { sheetName: "CSV" },
  );
  const [candidate] = normalizeRows(table, suggestMapping(table.headers), {
    dateOrder: "YMD",
    ambiguousDateConfirmed: false,
    decimalConvention: "dot",
    defaultCurrency: "INR",
  });
  assert.match(candidate.issues.join(" "), /Formula-like/);
});
