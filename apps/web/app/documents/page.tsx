"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  addMoney,
  type DocumentExtraction,
  type ReceiptCandidate,
} from "./document";

type Account = { id: string; name: string; currency: string };
type Category = { id: string; name: string; parent_id: string | null };
type Group = {
  id: string;
  name: string;
  members: { id: string; active?: boolean }[];
};
type ReceiptRecord = {
  id: string;
  version: number;
  status: string;
  matches: {
    transaction_id: string;
    description: string;
    date: string;
    amount: string;
    currency: string;
    evidence: string[];
    suggested: boolean;
  }[];
};
const apiUrl = "/api/backend";
const headers = {
  "Content-Type": "application/json",
};

export default function DocumentsPage() {
  const router = useRouter();
  const worker = useRef<Worker | undefined>(undefined);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [accounts, setAccounts] = useState<Account[]>([]),
    [categories, setCategories] = useState<Category[]>([]),
    [groups, setGroups] = useState<Group[]>([]);
  const [accountId, setAccountId] = useState(""),
    [groupId, setGroupId] = useState(""),
    [documentType, setDocumentType] =
      useState<DocumentExtraction["document_type"]>("receipt");
  const [file, setFile] = useState<File>(),
    [previewUrl, setPreviewUrl] = useState(""),
    [extraction, setExtraction] = useState<DocumentExtraction>(),
    [receipt, setReceipt] = useState<ReceiptCandidate>(),
    [record, setRecord] = useState<ReceiptRecord>(),
    [linkedId, setLinkedId] = useState("");
  const [progress, setProgress] = useState(0),
    [status, setStatus] = useState(
      "Choose a PDF or image. Processing stays in this browser.",
    ),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    Promise.all([
      fetch(`${apiUrl}/v1/accounts`, { headers }),
      fetch(`${apiUrl}/v1/categories`, { headers }),
      fetch(`${apiUrl}/v1/groups`, { headers }),
    ])
      .then(async (responses) => {
        if (responses.some((response) => !response.ok))
          throw new Error("Document services could not be loaded.");
        const [nextAccounts, nextCategories, nextGroups] = await Promise.all(
          responses.map((response) => response.json()),
        );
        setAccounts(nextAccounts);
        setCategories(nextCategories);
        setGroups(nextGroups);
        setAccountId(nextAccounts[0]?.id ?? "");
        setGroupId(nextGroups[0]?.id ?? "");
      })
      .catch((error) => setStatus(error.message));
    return () => {
      worker.current?.terminate();
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );
  function selectFile(next: File) {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(next);
    setPreviewUrl(
      next.type === "application/pdf" ? "" : URL.createObjectURL(next),
    );
    setExtraction(undefined);
    setReceipt(undefined);
    setRecord(undefined);
    setStatus("Ready for browser-local extraction.");
  }
  function choose(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0];
    if (next) selectFile(next);
  }
  function extract(forceOcr = false) {
    if (!file) return;
    setBusy(true);
    setProgress(0);
    setStatus("Inspecting document locally…");
    worker.current?.terminate();
    const next = new Worker(new URL("./document.worker.ts", import.meta.url));
    worker.current = next;
    timer.current = setTimeout(() => {
      next.terminate();
      setBusy(false);
      setStatus(
        "Processing exceeded 60 seconds. Use manual correction or a smaller, clearer document.",
      );
    }, 60_000);
    next.onmessage = (
      event: MessageEvent<{
        progress?: number;
        status?: string;
        result?: DocumentExtraction;
        preview?: Blob;
        error?: string;
      }>,
    ) => {
      if (event.data.progress !== undefined) {
        setProgress(event.data.progress);
        setStatus(event.data.status ?? "Processing locally…");
      }
      if (event.data.preview) {
        setPreviewUrl((current) => {
          if (current) URL.revokeObjectURL(current);
          return URL.createObjectURL(event.data.preview!);
        });
      }
      if (event.data.error) {
        if (timer.current) clearTimeout(timer.current);
        setBusy(false);
        setStatus(event.data.error);
      }
      if (event.data.result) {
        if (timer.current) clearTimeout(timer.current);
        setBusy(false);
        setExtraction(event.data.result);
        setReceipt(event.data.result.receipt);
        setStatus(
          event.data.result.used_ocr
            ? "OCR complete. Verify every extracted field."
            : "Text extracted without OCR. Verify every field.",
        );
      }
    };
    next.onerror = () => {
      setBusy(false);
      setStatus(
        "The local extraction worker stopped safely. Manual review remains available.",
      );
    };
    next.postMessage({ file, documentType, forceOcr });
  }
  function updateReceipt(changes: Partial<ReceiptCandidate>) {
    setReceipt((current) => (current ? { ...current, ...changes } : current));
    setRecord(undefined);
  }
  const calculated = useMemo(
    () =>
      receipt
        ? addMoney([
            ...receipt.items.map((item) => item.line_total),
            receipt.discount,
            receipt.tax,
            receipt.service_charge,
            receipt.tip,
            receipt.rounding,
          ])
        : "0.00",
    [receipt],
  );
  async function stage() {
    if (!file || !extraction) return;
    const source_hash = [
      ...new Uint8Array(
        await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
      ),
    ]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    if (documentType === "bank_statement") {
      if (!accountId || !extraction.transactions.length)
        return setStatus(
          "No complete statement rows were found. Use CSV/XLSX or manually correct the source.",
        );
      const response = await fetch(`${apiUrl}/v1/imports/stage`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          account_id: accountId,
          source_hash,
          file_name: file.name,
          file_format: "pdf",
          sheet_name: null,
          mapping: { source: "document-v1" },
          candidates: extraction.transactions,
        }),
      });
      const result = await response.json();
      if (!response.ok)
        return setStatus(result.detail ?? "Statement could not be staged.");
      router.push(`/imports?batch=${result.id}`);
      return;
    }
    if (!receipt || calculated !== Number(receipt.total || 0).toFixed(2))
      return setStatus(
        `Receipt components must reconcile exactly. Current calculation: ${calculated}.`,
      );
    const response = await fetch(`${apiUrl}/v1/receipts`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        idempotency_key: crypto.randomUUID(),
        account_id: accountId || null,
        source_hash,
        file_name: file.name,
        source_format: extraction.source_format,
        document_type: documentType,
        page_count: extraction.pages,
        used_ocr: extraction.used_ocr,
        elapsed_ms: extraction.elapsed_ms,
        candidate: receipt,
      }),
    });
    const result = await response.json();
    if (response.ok) {
      setRecord(result);
      setStatus(
        "Receipt staged. Choose a ledger match or open the reviewed components in Split Builder.",
      );
    } else
      setStatus(
        typeof result.detail === "string"
          ? result.detail
          : "Correct the highlighted financial fields.",
      );
  }
  async function confirm() {
    if (!record) return;
    const response = await fetch(`${apiUrl}/v1/receipts/${record.id}/confirm`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        expected_version: record.version,
        linked_transaction_id: linkedId || null,
      }),
    });
    const result = await response.json();
    if (response.ok) {
      setRecord(result);
      setStatus(
        linkedId
          ? "Receipt linked without creating a duplicate expense."
          : "Receipt confirmed as provenance without creating a ledger expense.",
      );
    } else setStatus(result.detail ?? "Receipt was not confirmed.");
  }
  function openSplit() {
    if (!receipt || !groupId || calculated !== Number(receipt.total).toFixed(2))
      return;
    const group = groups.find((item) => item.id === groupId);
    if (!group) return;
    const shares = group.members
      .filter((member) => member.active !== false)
      .map((member) => ({ member_id: member.id }));
    const components = [
      ...receipt.items.map((item) => ({
        label: item.label,
        amount: item.line_total,
        strategy: "equal",
        shares,
      })),
      ...[
        ["Discount", receipt.discount],
        ["Tax", receipt.tax],
        ["Service charge", receipt.service_charge],
        ["Tip", receipt.tip],
        ["Rounding", receipt.rounding],
      ]
        .filter(([, amount]) => amount !== "0.00" && amount !== "0")
        .map(([label, amount]) => ({
          label,
          amount,
          strategy: "equal",
          shares,
        })),
    ];
    sessionStorage.setItem(
      "expense-intelligence-template-draft",
      JSON.stringify({
        group_id: groupId,
        receipt_id: record?.status === "confirmed" ? record.id : undefined,
        description: receipt.merchant,
        total: receipt.total,
        currency: receipt.currency,
        expense_date: receipt.document_date,
        components,
      }),
    );
    router.push("/groups/new-expense");
  }
  const categoryOptions = categories.filter((category) => category.parent_id);
  return (
    <main className="imports-shell" id="main-content">
      <header className="topbar">
        <Link className="brand" href="/">
          <span>EI</span>Expense Intelligence
        </Link>
        <nav className="top-actions">
          <Link href="/imports">Statement imports</Link>
          <Link href="/groups">Split Builder</Link>
          <div className="environment">
            <i aria-hidden="true" /> Local document intelligence
          </div>
        </nav>
      </header>
      <section className="imports-heading">
        <div>
          <p className="eyebrow">PDF, OCR & receipts</p>
          <h1>Read locally. Reconcile exactly.</h1>
          <p className="lede">
            PDF.js and OCR run inside your browser. Original documents never
            reach the API or an AI provider.
          </p>
        </div>
      </section>
      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
      <nav className="panel entry-hub" aria-label="Add financial records">
        <div><p className="eyebrow">Choose a workflow</p><strong>What would you like to add?</strong></div>
        <Link href="/imports">Import CSV or Excel</Link>
        <Link href="/documents" aria-current="page">Scan Receipt or PDF</Link>
        <Link href="/transactions?add=true">Add Transaction</Link>
        <Link href="/groups">Open Split Builder</Link>
      </nav>
      <section
        className="panel document-source"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          const next = event.dataTransfer.files[0];
          if (next) selectFile(next);
        }}
      >
        <label>
          Document type
          <select
            value={documentType}
            onChange={(event) =>
              setDocumentType(event.target.value as typeof documentType)
            }
          >
            <option value="receipt">Receipt</option>
            <option value="itemized_bill">Itemized bill</option>
            <option value="bank_statement">Bank statement</option>
            <option value="other">Other document</option>
          </select>
        </label>
        <label>
          Financial account
          <select
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
          >
            <option value="">No account</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} · {account.currency}
              </option>
            ))}
          </select>
        </label>
        <label className="file-drop">
          PDF, JPG, PNG or WebP
          <input
            type="file"
            accept="application/pdf,image/jpeg,image/png,image/webp"
            capture="environment"
            onChange={choose}
          />
          <small>Drop here or use the camera · maximum 10 MiB</small>
        </label>
        <button disabled={!file || busy} onClick={() => extract(false)}>
          {busy
            ? `Processing ${Math.round(progress * 100)}%`
            : "Extract Locally"}
        </button>
        {extraction &&
        !extraction.used_ocr &&
        extraction.source_format === "pdf" ? (
          <button className="secondary" onClick={() => extract(true)}>
            Retry Pages with OCR
          </button>
        ) : null}
      </section>
      {previewUrl ? (
        <section className="panel document-preview">
          <h2>Source preview</h2>
          <Image
            src={previewUrl}
            alt="Selected financial document preview"
            width={1200}
            height={900}
            unoptimized
          />
        </section>
      ) : null}
      {extraction && documentType === "bank_statement" ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Statement review</p>
              <h2>{extraction.transactions.length} transaction candidates</h2>
            </div>
            <span>
              {extraction.pages} page(s) · {extraction.elapsed_ms} ms
            </span>
          </div>
          <div className="staged-list">
            {extraction.transactions.slice(0, 200).map((row) => (
              <article key={row.source_row}>
                <div>
                  <strong>{row.description}</strong>
                  <span>
                    {row.transaction_date} · {row.currency} {row.amount} ·{" "}
                    {row.direction}
                  </span>
                </div>
              </article>
            ))}
          </div>
          <button onClick={stage}>Stage in Existing Import Review</button>
        </section>
      ) : null}
      {receipt && documentType !== "bank_statement" ? (
        <section className="panel receipt-review">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Editable extraction</p>
              <h2>Receipt evidence</h2>
            </div>
            <span>
              Confidence {Math.round(receipt.confidence * 100)}% ·{" "}
              {extraction?.elapsed_ms} ms
            </span>
          </div>
          <div className="form-row">
            <label>
              Merchant
              <input
                value={receipt.merchant}
                onChange={(event) =>
                  updateReceipt({ merchant: event.target.value })
                }
              />
            </label>
            <label>
              Date
              <input
                type="date"
                value={receipt.document_date}
                onChange={(event) =>
                  updateReceipt({ document_date: event.target.value })
                }
              />
            </label>
            <label>
              Currency
              <select
                value={receipt.currency}
                onChange={(event) =>
                  updateReceipt({ currency: event.target.value })
                }
              >
                <option>INR</option>
                <option>GBP</option>
              </select>
            </label>
            <label>
              Final total
              <input
                inputMode="decimal"
                value={receipt.total}
                onChange={(event) =>
                  updateReceipt({ total: event.target.value })
                }
              />
            </label>
          </div>
          <div className="receipt-items">
            {receipt.items.map((item, index) => (
              <article key={index}>
                <input
                  aria-label={`Item ${index + 1} label`}
                  value={item.label}
                  onChange={(event) =>
                    updateReceipt({
                      items: receipt.items.map((row, itemIndex) =>
                        itemIndex === index
                          ? { ...row, label: event.target.value }
                          : row,
                      ),
                    })
                  }
                />
                <input
                  aria-label={`Item ${index + 1} quantity`}
                  value={item.quantity}
                  onChange={(event) =>
                    updateReceipt({
                      items: receipt.items.map((row, itemIndex) =>
                        itemIndex === index
                          ? { ...row, quantity: event.target.value }
                          : row,
                      ),
                    })
                  }
                />
                <input
                  aria-label={`Item ${index + 1} total`}
                  inputMode="decimal"
                  value={item.line_total}
                  onChange={(event) =>
                    updateReceipt({
                      items: receipt.items.map((row, itemIndex) =>
                        itemIndex === index
                          ? {
                              ...row,
                              line_total: event.target.value,
                              unit_price: event.target.value,
                            }
                          : row,
                      ),
                    })
                  }
                />
                <select
                  aria-label={`Item ${index + 1} category`}
                  value={item.category_id ?? ""}
                  onChange={(event) =>
                    updateReceipt({
                      items: receipt.items.map((row, itemIndex) =>
                        itemIndex === index
                          ? {
                              ...row,
                              category_id: event.target.value || undefined,
                            }
                          : row,
                      ),
                    })
                  }
                >
                  <option value="">Uncategorized</option>
                  {categoryOptions.map((category) => (
                    <option value={category.id} key={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
                <button
                  className="danger"
                  onClick={() =>
                    updateReceipt({
                      items: receipt.items.filter(
                        (_, itemIndex) => itemIndex !== index,
                      ),
                    })
                  }
                >
                  Remove
                </button>
              </article>
            ))}
          </div>
          <button
            className="secondary"
            onClick={() =>
              updateReceipt({
                items: [
                  ...receipt.items,
                  {
                    label: "",
                    quantity: "1",
                    unit_price: "0.00",
                    line_total: "0.00",
                  },
                ],
              })
            }
          >
            Add Item
          </button>
          <div className="receipt-charges">
            {(
              ["discount", "tax", "service_charge", "tip", "rounding"] as const
            ).map((field) => (
              <label key={field}>
                {field.replace("_", " ")}
                <input
                  inputMode="decimal"
                  value={receipt[field]}
                  onChange={(event) =>
                    updateReceipt({ [field]: event.target.value })
                  }
                />
              </label>
            ))}
          </div>
          <p
            className={
              calculated === Number(receipt.total || 0).toFixed(2)
                ? "reconciled"
                : "validation-error"
            }
          >
            Components{" "}
            {calculated === Number(receipt.total || 0).toFixed(2)
              ? "reconcile exactly"
              : `total ${calculated}; expected ${receipt.total || "0.00"}`}
          </p>
          {!record ? (
            <button onClick={stage}>Stage Reviewed Receipt</button>
          ) : (
            <>
              <label>
                Matching transaction
                <select
                  value={linkedId}
                  onChange={(event) => setLinkedId(event.target.value)}
                >
                  <option value="">No ledger link</option>
                  {record.matches.map((match) => (
                    <option
                      value={match.transaction_id}
                      key={match.transaction_id}
                    >
                      {match.suggested ? "Suggested · " : ""}
                      {match.date} · {match.description} · {match.currency}{" "}
                      {match.amount}
                    </option>
                  ))}
                </select>
              </label>
              <button
                disabled={record.status === "confirmed"}
                onClick={confirm}
              >
                Confirm Receipt {linkedId ? "and Link" : "Provenance"}
              </button>
              <div className="split-handoff">
                <label>
                  Group
                  <select
                    value={groupId}
                    onChange={(event) => setGroupId(event.target.value)}
                  >
                    {groups.map((group) => (
                      <option value={group.id} key={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="secondary"
                  disabled={!groupId}
                  onClick={openSplit}
                >
                  Open in Universal Split Builder
                </button>
              </div>
            </>
          )}
        </section>
      ) : null}
    </main>
  );
}
