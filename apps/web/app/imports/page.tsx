"use client";

import Link from "next/link";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  ColumnMapping,
  FinancialField,
  NormalizedCandidate,
  ParsedTable,
  normalizeRows,
  suggestMapping,
} from "./tabular";

type Account = { id: string; name: string; currency: string };
type Category = { id: string; name: string; parent_id: string | null };
type BatchRow = NormalizedCandidate & {
  id: string;
  category_id?: string;
  review_state: string;
  duplicate_kind?: string;
  duplicate_transaction_id?: string;
  issues: string[];
};
type Batch = {
  id: string;
  file_name: string;
  status: string;
  version: number;
  row_count: number;
  accepted_count: number;
  excluded_count: number;
  duplicate_count: number;
  invalid_count: number;
  rows: BatchRow[];
};
type History = {
  id: string;
  file_name: string;
  file_format: string;
  status: string;
  row_count: number;
  accepted_count: number;
  duplicate_count: number;
  created_at: string;
};
const apiUrl = "/api/backend";
const headers = {
  "Content-Type": "application/json",
};
const fields: { value: FinancialField; label: string }[] = [
  { value: "ignore", label: "Ignore" },
  { value: "transaction_date", label: "Transaction date" },
  { value: "posting_date", label: "Posting date" },
  { value: "description", label: "Description / merchant" },
  { value: "amount", label: "Signed amount" },
  { value: "debit", label: "Debit / withdrawal" },
  { value: "credit", label: "Credit / deposit" },
  { value: "currency", label: "Currency" },
  { value: "reference", label: "Reference" },
];
function addDecimal(left: string, right: string) {
  const units = (value: string) => {
    const [whole, fraction = ""] = value.split(".");
    return (
      BigInt(whole) * 1_000_000_000_000n +
      BigInt(fraction.padEnd(12, "0").slice(0, 12))
    );
  };
  const sum = units(left) + units(right);
  const whole = sum / 1_000_000_000_000n,
    fraction = (sum % 1_000_000_000_000n)
      .toString()
      .padStart(12, "0")
      .replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : whole.toString();
}

export default function ImportsPage() {
  const worker = useRef<Worker | undefined>(undefined);
  const [selectedFile, setSelectedFile] = useState<File>();
  const [accounts, setAccounts] = useState<Account[]>([]),
    [categories, setCategories] = useState<Category[]>([]),
    [history, setHistory] = useState<History[]>([]);
  const [accountId, setAccountId] = useState(""),
    [table, setTable] = useState<ParsedTable>(),
    [mapping, setMapping] = useState<ColumnMapping>({}),
    [candidates, setCandidates] = useState<
      (NormalizedCandidate & { category_id?: string })[]
    >([]),
    [batch, setBatch] = useState<Batch>();
  const [dateOrder, setDateOrder] = useState<"DMY" | "MDY" | "YMD">("DMY"),
    [ambiguousDateConfirmed, setAmbiguousDateConfirmed] = useState(false),
    [decimalConvention, setDecimalConvention] = useState<"dot" | "comma">(
      "dot",
    ),
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState(""),
    [bulkCategory, setBulkCategory] = useState(""),
    [batchKey, setBatchKey] = useState(""),
    [staging, setStaging] = useState(false),
    [status, setStatus] = useState(
      "Choose an account and a CSV or XLSX statement.",
    );
  const account = accounts.find((item) => item.id === accountId);
  async function refresh() {
    const responses = await Promise.all([
      fetch(`${apiUrl}/v1/accounts`, { headers }),
      fetch(`${apiUrl}/v1/categories`, { headers }),
      fetch(`${apiUrl}/v1/imports`, { headers }),
    ]);
    if (responses.some((response) => !response.ok))
      throw new Error("Import services could not be loaded.");
    const [nextAccounts, nextCategories, nextHistory] = await Promise.all(
      responses.map((response) => response.json()),
    );
    setAccounts(nextAccounts);
    setCategories(nextCategories);
    setHistory(nextHistory);
    setAccountId((current) => current || nextAccounts[0]?.id || "");
  }
  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(`${apiUrl}/v1/accounts`, { headers }),
      fetch(`${apiUrl}/v1/categories`, { headers }),
      fetch(`${apiUrl}/v1/imports`, { headers }),
    ])
      .then(async (responses) => {
        if (responses.some((response) => !response.ok))
          throw new Error("Import services could not be loaded.");
        const [nextAccounts, nextCategories, nextHistory] = await Promise.all(
          responses.map((response) => response.json()),
        );
        if (active) {
          setAccounts(nextAccounts);
          setCategories(nextCategories);
          setHistory(nextHistory);
          setAccountId(nextAccounts[0]?.id ?? "");
          const batchId = new URLSearchParams(window.location.search).get(
            "batch",
          );
          if (batchId) {
            const response = await fetch(`${apiUrl}/v1/imports/${batchId}`, {
              headers,
            });
            if (response.ok) {
              setBatch(await response.json());
              setStatus(
                "Document candidates are staged for duplicate review and explicit confirmation.",
              );
            }
          }
        }
      })
      .catch((error) => {
        if (active) setStatus(error.message);
      });
    return () => {
      active = false;
      worker.current?.terminate();
    };
  }, []);
  async function createAccount() {
    const name = window.prompt("Account name, e.g. Current account");
    const currency = window.prompt("Account currency", "INR")?.toUpperCase();
    if (!name || !currency) return;
    const response = await fetch(`${apiUrl}/v1/accounts`, {
      method: "POST",
      headers,
      body: JSON.stringify({ name, currency }),
    });
    if (response.ok) {
      await refresh();
      setStatus("Account created.");
    } else
      setStatus(
        (await response.json()).detail ?? "Account could not be created.",
      );
  }
  function parse(file: File, sheetName?: string) {
    setSelectedFile(file);
    setBatchKey(crypto.randomUUID());
    setStatus("Parsing locally in your browser…");
    worker.current?.terminate();
    const next = new Worker(new URL("./parser.worker.ts", import.meta.url));
    worker.current = next;
    next.onmessage = (
      event: MessageEvent<ParsedTable & { error?: string }>,
    ) => {
      if (event.data.error) return setStatus(event.data.error);
      setTable(event.data);
      const suggested = suggestMapping(event.data.headers);
      setMapping(suggested);
      setCandidates([]);
      setBatch(undefined);
      setStatus("Confirm the detected header and column mapping.");
    };
    next.onerror = () =>
      setStatus("The local parser stopped safely. Check the file format.");
    next.postMessage({ file, sheetName });
  }
  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) parse(file);
  }
  function buildPreview() {
    if (!table || !account) return;
    try {
      const next = normalizeRows(table, mapping, {
        dateOrder,
        ambiguousDateConfirmed,
        decimalConvention,
        defaultCurrency: account.currency,
      });
      setCandidates(next);
      setStatus(
        next.some((row) => row.issues.length)
          ? "Resolve highlighted rows before staging."
          : "Review every normalized value. Nothing has been uploaded yet.",
      );
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "Mapping is incomplete.",
      );
    }
  }
  function editCandidate(
    index: number,
    changes: Partial<NormalizedCandidate & { category_id?: string }>,
  ) {
    setCandidates((rows) =>
      rows.map((row, rowIndex) =>
        rowIndex === index ? { ...row, ...changes, issues: [] } : row,
      ),
    );
  }
  async function stage() {
    if (
      !selectedFile ||
      !account ||
      !table ||
      candidates.some((row) => row.issues.length)
    )
      return setStatus("Resolve validation issues before staging.");
    setStaging(true);
    const hash = [
      ...new Uint8Array(
        await crypto.subtle.digest("SHA-256", await selectedFile.arrayBuffer()),
      ),
    ]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    try {
      const response = await fetch(`${apiUrl}/v1/imports/stage`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          idempotency_key: batchKey || crypto.randomUUID(),
          account_id: account.id,
          source_hash: hash,
          file_name: selectedFile.name,
          file_format: selectedFile.name.toLowerCase().endsWith(".xlsx")
            ? "xlsx"
            : "csv",
          sheet_name: table.sheetName,
          mapping,
          mapping_profile_name: `Saved mapping · ${selectedFile.name.split(".").pop()?.toUpperCase()}`,
          candidates,
        }),
      });
      const result = await response.json();
      if (response.ok) {
        setBatch(result);
        worker.current?.terminate();
        worker.current = undefined;
        setSelectedFile(undefined);
        setStatus(
          "Structured candidates staged. Raw file bytes stayed in this browser.",
        );
        await refresh();
      } else setStatus(result.detail ?? "Import could not be staged.");
    } finally {
      setStaging(false);
    }
  }
  async function decide(row: BatchRow, duplicate_action: "import" | "exclude") {
    if (!batch) return;
    const response = await fetch(
      `${apiUrl}/v1/imports/${batch.id}/rows/${row.id}`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify({
          expected_batch_version: batch.version,
          duplicate_action,
        }),
      },
    );
    const result = await response.json();
    if (response.ok) {
      setBatch(result);
      setStatus("Review decision saved.");
    } else setStatus(result.detail ?? "Decision could not be saved.");
  }
  async function confirm() {
    if (
      !batch ||
      !window.confirm(
        `Import approved rows from “${batch.file_name}”? This writes to your ledger.`,
      )
    )
      return;
    const response = await fetch(`${apiUrl}/v1/imports/${batch.id}/confirm`, {
      method: "POST",
      headers,
      body: JSON.stringify({ expected_version: batch.version }),
    });
    const result = await response.json();
    if (response.ok) {
      setBatch(result);
      setStatus(
        "Import committed atomically. Transactions are now available in dashboards and budgets.",
      );
      await refresh();
    } else setStatus(result.detail ?? "Import was not committed.");
  }
  const visible = useMemo(
    () =>
      (batch?.rows ?? []).filter(
        (row) =>
          row.description.toLowerCase().includes(search.toLowerCase()) &&
          (filter === "all" ||
            (filter === "duplicate"
              ? row.duplicate_kind
              : filter === "review"
                ? row.review_state === "needs_review"
                : !row.category_id)),
      ),
    [batch, filter, search],
  );
  const categoryOptions = categories.filter((category) => category.parent_id);
  const totals = useMemo(
    () =>
      candidates
        .filter((row) => row.included)
        .reduce<Record<string, string>>((result, row) => {
          result[row.currency] = addDecimal(
            result[row.currency] ?? "0",
            row.amount,
          );
          return result;
        }, {}),
    [candidates],
  );
  return (
    <main className="imports-shell" id="main-content">
      <header className="topbar">
        <Link className="brand" href="/">
          <span>EI</span>Expense Intelligence
        </Link>
        <nav className="top-actions">
          <Link href="/transactions">Transactions</Link>
          <Link href="/groups">Groups</Link>
          <Link href="/documents">PDF & Receipts</Link>
          <div className="environment">
            <i aria-hidden="true" /> Browser-local parsing
          </div>
        </nav>
      </header>
      <section className="imports-heading">
        <div>
          <p className="eyebrow">Document ingestion</p>
          <h1>From statement to ledger, with you in control.</h1>
          <p className="lede">
            CSV and XLSX bytes are parsed locally. Only the structured rows you
            review are sent for secure staging.
          </p>
        </div>
        <ol className="import-steps">
          <li className={!table ? "active" : "done"}>1 · Select</li>
          <li
            className={
              table && !candidates.length
                ? "active"
                : candidates.length
                  ? "done"
                  : ""
            }
          >
            2 · Map
          </li>
          <li
            className={
              candidates.length && !batch ? "active" : batch ? "done" : ""
            }
          >
            3 · Review
          </li>
          <li className={batch ? "active" : ""}>4 · Confirm</li>
        </ol>
      </section>
      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
      <nav className="panel entry-hub" aria-label="Add financial records">
        <div><p className="eyebrow">Choose a workflow</p><strong>What would you like to add?</strong></div>
        <Link href="/imports" aria-current="page">Import Bank Statement</Link>
        <Link href="/documents">Scan Receipt or PDF</Link>
        <Link href="/transactions?add=true">Add Transaction</Link>
        <Link href="/documents">Split Receipt</Link>
      </nav>
      <section className="panel import-source">
        <div>
          <p className="eyebrow">Source</p>
          <h2>Select an account and statement</h2>
        </div>
        <label>
          Financial account
          <select
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
          >
            <option value="">Choose an account…</option>
            {accounts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.currency}
              </option>
            ))}
          </select>
        </label>
        <button className="secondary" onClick={createAccount}>
          New Account
        </button>
        <label className="file-drop">
          CSV or XLSX
          <input
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={chooseFile}
            disabled={!accountId}
          />
          <span>Maximum 10 MiB · 10,000 rows · original file stays local</span>
        </label>
      </section>
      {table ? (
        <section className="panel import-mapping">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Column mapping</p>
              <h2>{selectedFile?.name}</h2>
            </div>
            {table.sheetNames.length > 1 ? (
              <label>
                Sheet
                <select
                  value={table.sheetName}
                  onChange={(event) =>
                    selectedFile && parse(selectedFile, event.target.value)
                  }
                >
                  {table.sheetNames.map((sheet) => (
                    <option key={sheet}>{sheet}</option>
                  ))}
                </select>
              </label>
            ) : (
              <span>
                {table.encoding ?? "XLSX"}
                {table.delimiter ? ` · “${table.delimiter}” delimiter` : ""}
              </span>
            )}
          </div>
          <div className="mapping-grid">
            {table.headers.map((header) => (
              <label key={header}>
                <span>
                  {header}
                  <small>
                    {table.rows[0]?.[table.headers.indexOf(header)] ||
                      "Blank sample"}
                  </small>
                </span>
                <select
                  value={mapping[header] ?? "ignore"}
                  onChange={(event) =>
                    setMapping((current) => ({
                      ...current,
                      [header]: event.target.value as FinancialField,
                    }))
                  }
                >
                  {fields.map((field) => (
                    <option key={field.value} value={field.value}>
                      {field.label}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <div className="mapping-options">
            <label>
              Date interpretation
              <select
                value={dateOrder}
                onChange={(event) => {
                  setDateOrder(event.target.value as typeof dateOrder);
                  setAmbiguousDateConfirmed(false);
                }}
              >
                <option value="DMY">Day / Month / Year</option>
                <option value="MDY">Month / Day / Year</option>
                <option value="YMD">Year / Month / Day</option>
              </select>
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={ambiguousDateConfirmed}
                onChange={(event) =>
                  setAmbiguousDateConfirmed(event.target.checked)
                }
              />
              Confirm this order for ambiguous dates
            </label>
            <label>
              Number format
              <select
                value={decimalConvention}
                onChange={(event) =>
                  setDecimalConvention(
                    event.target.value as typeof decimalConvention,
                  )
                }
              >
                <option value="dot">1,234.56</option>
                <option value="comma">1.234,56</option>
              </select>
            </label>
            <button onClick={buildPreview}>Build Local Preview</button>
          </div>
        </section>
      ) : null}
      {candidates.length && !batch ? (
        <section className="panel import-review">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Local review</p>
              <h2>Normalized transactions</h2>
            </div>
            <span>
              {candidates.filter((row) => row.included).length} included ·{" "}
              {Object.entries(totals)
                .map(([currency, amount]) => `${currency} ${amount}`)
                .join(" / ")}
            </span>
          </div>
          <div className="review-toolbar">
            <label>
              Category for included rows
              <select
                value={bulkCategory}
                onChange={(event) => setBulkCategory(event.target.value)}
              >
                <option value="">Choose a category</option>
                {categoryOptions.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="secondary"
              disabled={!bulkCategory}
              onClick={() =>
                setCandidates((rows) =>
                  rows.map((row) =>
                    row.included ? { ...row, category_id: bulkCategory } : row,
                  ),
                )
              }
            >
              Apply to Included
            </button>
          </div>
          <div className="import-table">
            {candidates.map((row, index) => (
              <article
                className={row.issues.length ? "invalid" : ""}
                key={row.source_row}
              >
                <label className="check">
                  <input
                    type="checkbox"
                    checked={row.included}
                    onChange={(event) =>
                      editCandidate(index, { included: event.target.checked })
                    }
                  />{" "}
                  Row {row.source_row}
                </label>
                <input
                  aria-label={`Row ${row.source_row} date`}
                  type="date"
                  value={row.transaction_date}
                  onChange={(event) =>
                    editCandidate(index, {
                      transaction_date: event.target.value,
                    })
                  }
                />
                <input
                  aria-label={`Row ${row.source_row} description`}
                  value={row.description}
                  onChange={(event) =>
                    editCandidate(index, { description: event.target.value })
                  }
                />
                <select
                  aria-label={`Row ${row.source_row} direction`}
                  value={row.direction}
                  onChange={(event) =>
                    editCandidate(index, {
                      direction: event.target
                        .value as NormalizedCandidate["direction"],
                    })
                  }
                >
                  <option value="expense">Expense</option>
                  <option value="income">Income</option>
                  <option value="transfer">Transfer</option>
                </select>
                <input
                  aria-label={`Row ${row.source_row} amount`}
                  inputMode="decimal"
                  value={row.amount}
                  onChange={(event) =>
                    editCandidate(index, { amount: event.target.value })
                  }
                />
                <input
                  aria-label={`Row ${row.source_row} currency`}
                  maxLength={3}
                  value={row.currency}
                  onChange={(event) =>
                    editCandidate(index, {
                      currency: event.target.value.toUpperCase(),
                    })
                  }
                />
                <select
                  aria-label={`Row ${row.source_row} category`}
                  value={row.category_id ?? ""}
                  onChange={(event) =>
                    setCandidates((rows) =>
                      rows.map((item, itemIndex) =>
                        itemIndex === index
                          ? {
                              ...item,
                              category_id: event.target.value || undefined,
                            }
                          : item,
                      ),
                    )
                  }
                >
                  <option value="">Uncategorized</option>
                  {categoryOptions.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
                {row.issues.length ? (
                  <small>{row.issues.join(" · ")}</small>
                ) : null}
              </article>
            ))}
          </div>
          <button
            disabled={staging || candidates.some((row) => row.issues.length)}
            onClick={stage}
          >
            {staging ? "Staging…" : "Stage Reviewed Candidates"}
          </button>
        </section>
      ) : null}
      {batch ? (
        <section className="panel staged-review">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Secure staging</p>
              <h2>{batch.file_name}</h2>
            </div>
            <span>
              {batch.status} · version {batch.version}
            </span>
          </div>
          <div className="review-counts">
            <span>{batch.row_count} rows</span>
            <span>{batch.duplicate_count} duplicates</span>
            <span>{batch.invalid_count} invalid</span>
            <span>{batch.excluded_count} excluded</span>
          </div>
          <div className="review-toolbar">
            <label>
              Search
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Merchant or description"
              />
            </label>
            <label>
              Filter
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
              >
                <option value="all">All rows</option>
                <option value="review">Needs review</option>
                <option value="duplicate">Duplicates</option>
                <option value="uncategorized">Uncategorized</option>
              </select>
            </label>
          </div>
          <div className="staged-list">
            {visible.map((row) => (
              <article key={row.id}>
                <div>
                  <strong>{row.description}</strong>
                  <span>
                    {row.transaction_date} · {row.currency} {row.amount} ·{" "}
                    {row.direction}
                  </span>
                  {row.duplicate_kind ? (
                    <em>
                      {row.duplicate_kind} duplicate · {row.issues.join(" · ")}
                    </em>
                  ) : row.issues.length ? (
                    <em>{row.issues.join(" · ")}</em>
                  ) : null}
                </div>
                <span className={`review-state ${row.review_state}`}>
                  {row.review_state.replace("_", " ")}
                </span>
                {row.review_state === "needs_review" ? (
                  <div>
                    <button
                      className="secondary"
                      onClick={() => decide(row, "import")}
                    >
                      Import Anyway
                    </button>
                    <button
                      className="danger"
                      onClick={() => decide(row, "exclude")}
                    >
                      Exclude
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
          {batch.status === "review" ? (
            <button
              disabled={batch.rows.some(
                (row) => row.review_state === "needs_review",
              )}
              onClick={confirm}
            >
              Confirm Atomic Import
            </button>
          ) : (
            <Link className="button-link" href="/transactions">
              View Imported Transactions
            </Link>
          )}
        </section>
      ) : null}
      <section className="panel import-history">
        <p className="eyebrow">Provenance</p>
        <h2>Import history</h2>
        {history.length ? (
          history.map((item) => (
            <div className="finance-row" key={item.id}>
              <span>
                {item.file_name}
                <small>
                  {new Intl.DateTimeFormat("en-GB", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(item.created_at))}{" "}
                  · {item.file_format.toUpperCase()} · {item.status}
                </small>
              </span>
              <b>
                {item.accepted_count}/{item.row_count}
              </b>
            </div>
          ))
        ) : (
          <p className="muted">No imports yet.</p>
        )}
      </section>
    </main>
  );
}
