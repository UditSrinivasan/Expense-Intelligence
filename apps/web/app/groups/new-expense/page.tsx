"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChangeEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { type DocumentExtraction, type ReceiptCandidate } from "../../documents/document";

type Member = {
  id: string;
  display_name: string;
  role: string;
  is_guest: boolean;
};
type Group = {
  id: string;
  name: string;
  default_currency: string;
  archived: boolean;
  members: Member[];
};
type Category = { id: string; name: string; parent_id: string | null };
type Strategy =
  "equal" | "percentage" | "exact" | "weighted" | "quantity" | "usage" | "time";
type Kind = "item" | "discount" | "tax" | "service_charge" | "delivery" | "packaging" | "tip" | "rounding";
type Component = {
  id: string;
  label: string;
  amount: string;
  quantity: string;
  unitPrice: string;
  strategy: Strategy;
  policy: "proportional" | "equal" | "custom";
  kind: Kind;
  categoryId?: string;
  included: Record<string, boolean>;
  values: Record<string, string>;
  confidence?: number;
  nonDiscountable?: boolean;
  promotionId?: string;
  discountMode?: "fixed" | "percentage" | "cashback";
  percentage?: string;
  cap?: string;
  minimumOrder?: string;
  eligibleItemIds?: string[];
};
type Preview = {
  allocations: {
    member_id: string;
    component_label: string;
    amount: string;
    received_residual: boolean;
  }[];
  balances: {
    member_id: string;
    paid: string;
    owed: string;
    balance: string;
  }[];
  components?: { index: number; label: string; kind: Kind; amount: string; basis: string | null; mode?: string }[];
};
type ReceiptRecord = {
  id: string;
  version: number;
  status: string;
  linked_transaction_id: string | null;
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
const headers = { "Content-Type": "application/json" };
const steps = [
  "Details",
  "People & Payers",
  "Items & Splitting",
  "Taxes & Charges",
  "Review & Confirm",
];
const today = new Date().toISOString().slice(0, 10);
const currencies = ["INR", "GBP", "USD", "EUR", "JPY", "KWD"];

function freshComponent(
  label = "Item",
  kind: Kind = "item",
  amount = "",
  index = 0,
): Component {
  return {
    id: `${Date.now()}-${index}-${crypto.randomUUID()}`,
    label,
    amount,
    quantity: "1",
    unitPrice: amount,
    strategy: "equal",
    policy: kind === "item" ? "equal" : "proportional",
    kind,
    included: {},
    values: {},
  };
}

function sumMoney(values: string[], currency: string): string {
  const places = currency === "JPY" ? 0 : currency === "KWD" ? 3 : 2;
  const scale = 10n ** BigInt(places);
  const units = values.reduce((sum, raw) => {
    const value = raw || "0", negative = value.startsWith("-");
    const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
    const next = BigInt(whole || "0") * scale + BigInt(fraction.padEnd(places, "0").slice(0, places) || "0");
    return sum + (negative ? -next : next);
  }, 0n);
  const sign = units < 0 ? "-" : "", absolute = units < 0 ? -units : units;
  return places ? `${sign}${absolute / scale}.${(absolute % scale).toString().padStart(places, "0")}` : `${sign}${absolute}`;
}

export default function GuidedExpensePage() {
  const router = useRouter();
  const worker = useRef<Worker | undefined>(undefined),
    timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [groups, setGroups] = useState<Group[]>([]),
    [categories, setCategories] = useState<Category[]>([]);
  const [groupId, setGroupId] = useState(""),
    [step, setStep] = useState(0);
  const [description, setDescription] = useState(""),
    [date, setDate] = useState(today),
    [currency, setCurrency] = useState("INR"),
    [total, setTotal] = useState("");
  const [components, setComponents] = useState<Component[]>([freshComponent()]);
  const [participants, setParticipants] = useState<Record<string, boolean>>({}),
    [payers, setPayers] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview>(),
    [idempotencyKey] = useState(() => crypto.randomUUID());
  const [status, setStatus] = useState("Loading your groups…"),
    [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File>(),
    [extraction, setExtraction] = useState<DocumentExtraction>(),
    [receipt, setReceipt] = useState<ReceiptCandidate>();
  const [receiptRecord, setReceiptRecord] = useState<ReceiptRecord>(),
    [linkedId, setLinkedId] = useState("");
  const selected = groups.find((group) => group.id === groupId);
  const names = useMemo(
    () =>
      new Map(
        selected?.members.map((member) => [member.id, member.display_name]) ??
          [],
      ),
    [selected],
  );
  const activeMembers =
    selected?.members.filter((member) => participants[member.id]) ?? [];
  const itemComponents = components.filter((row) => row.kind === "item"),
    chargeComponents = components.filter((row) => row.kind !== "item");
  const componentTotal = useMemo(
    () => sumMoney(components.map((row) => row.amount || "0"), currency),
    [components, currency],
  );
  const hasCalculatedDiscount = components.some(
    (row) => row.kind === "discount" && row.discountMode === "percentage",
  );
  const reconciled = total !== "" && componentTotal === sumMoney([total], currency);

  useEffect(() => {
    Promise.all([
      fetch(`${apiUrl}/v1/groups`, { headers }),
      fetch(`${apiUrl}/v1/categories`, { headers }),
    ])
      .then(async ([groupResponse, categoryResponse]) => {
        if (!groupResponse.ok || !categoryResponse.ok)
          throw new Error("The split builder could not be loaded.");
        const [nextGroups, nextCategories] = (await Promise.all([
          groupResponse.json(),
          categoryResponse.json(),
        ])) as [Group[], Category[]];
      const preferred = new URLSearchParams(window.location.search).get("group"),
          nextId = nextGroups.some((group) => group.id === preferred)
            ? preferred!
            : (nextGroups[0]?.id ?? ""),
          next = nextGroups.find((group) => group.id === nextId);
        setGroups(nextGroups);
        setCategories(nextCategories);
        setGroupId(nextId);
        setCurrency(next?.default_currency ?? "INR");
        setParticipants(
          Object.fromEntries(
            (next?.members ?? []).map((member) => [member.id, true]),
          ),
        );
        const stored = sessionStorage.getItem(
          "expense-intelligence-template-draft",
        );
        if (stored) {
          const draft = JSON.parse(stored) as {
            group_id?: string;
            receipt_id?: string;
            description?: string;
            total?: string;
            currency?: string;
            expense_date?: string;
            components?: {
              label: string;
              amount: string;
              strategy: Strategy;
              category_id?: string;
              shares: { member_id: string; value?: string }[];
            }[];
          };
          if (
            draft.group_id &&
            nextGroups.some((group) => group.id === draft.group_id)
          )
            setGroupId(draft.group_id);
          setDescription(draft.description ?? "");
          setTotal(draft.total ?? "");
          setCurrency(draft.currency ?? next?.default_currency ?? "INR");
          setDate(draft.expense_date ?? today);
          if (draft.components?.length)
            setComponents(
              draft.components.map((row, index) => ({
                ...freshComponent(
                  row.label,
                  kindFor(row.label),
                  row.amount,
                  index,
                ),
                strategy: row.strategy,
                categoryId: row.category_id,
                included: Object.fromEntries(
                  row.shares.map((share) => [share.member_id, true]),
                ),
                values: Object.fromEntries(
                  row.shares.map((share) => [
                    share.member_id,
                    share.value ?? "",
                  ]),
                ),
              })),
            );
          if (draft.receipt_id)
            fetch(`${apiUrl}/v1/receipts/${draft.receipt_id}`, { headers })
              .then((response) => (response.ok ? response.json() : undefined))
              .then((record) => record && setReceiptRecord(record));
          sessionStorage.removeItem("expense-intelligence-template-draft");
        }
        setStatus(
          "Start manually or extract a receipt locally in this browser.",
        );
      })
      .catch((error: Error) => setStatus(error.message));
    return () => {
      worker.current?.terminate();
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  function selectGroup(nextId: string) {
    const next = groups.find((group) => group.id === nextId);
    setGroupId(nextId);
    setCurrency(next?.default_currency ?? "INR");
    setParticipants(
      Object.fromEntries(
        (next?.members ?? []).map((member) => [member.id, true]),
      ),
    );
    setPayers({});
    setPreview(undefined);
  }
  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0];
    if (!next) return;
    setFile(next);
    setExtraction(undefined);
    setReceipt(undefined);
    setReceiptRecord(undefined);
    setStatus("Ready for local extraction.");
  }
  function extract() {
    if (!file) return;
    setBusy(true);
    setStatus("Reading the receipt locally…");
    worker.current?.terminate();
    const next = new Worker(
      new URL("../../documents/document.worker.ts", import.meta.url),
    );
    worker.current = next;
    timer.current = setTimeout(() => {
      next.terminate();
      setBusy(false);
      setStatus(
        "Extraction stopped at the 60-second safety limit. Enter the bill manually or use a smaller image.",
      );
    }, 60_000);
    next.onmessage = (
      event: MessageEvent<{
        status?: string;
        result?: DocumentExtraction;
        error?: string;
      }>,
    ) => {
      if (event.data.status) setStatus(event.data.status);
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
        const found = event.data.result.receipt;
        setDescription(found.merchant);
        setDate(found.document_date || today);
        setCurrency(found.currency);
        setTotal(found.total);
        const nextComponents = [
          ...found.items.map((item, index) => ({
            ...freshComponent(item.label, "item", item.line_total, index),
            quantity: item.quantity,
            unitPrice: item.unit_price,
            categoryId: item.category_id,
            confidence: item.evidence?.confidence,
          })),
          ...(
            [
              ["Discount", "discount", found.discount],
              ["Tax / GST / VAT", "tax", found.tax],
              ["Service charge", "service_charge", found.service_charge],
              ["Delivery fee", "delivery", found.delivery_fee],
              ["Packaging fee", "packaging", found.packaging_fee],
              ["Tip", "tip", found.tip],
              ["Rounding", "rounding", found.rounding],
            ] as [string, Kind, string][]
          )
            .filter(([, , amount]) => amount !== "0" && amount !== "0.00")
            .map(([label, kind, amount], index) =>
              freshComponent(label, kind, amount, found.items.length + index),
            ),
        ];
        setComponents(
          nextComponents.length ? nextComponents : [freshComponent()],
        );
        setStatus(
          found.confidence < 0.7 || found.issues.length
            ? "Extraction needs review. Correct uncertain fields and reconcile the total before continuing."
            : "Receipt extracted locally. Verify every field before continuing.",
        );
      }
    };
    next.onerror = () => {
      setBusy(false);
      setStatus(
        "The local extraction worker stopped safely. Manual entry remains available.",
      );
    };
    next.postMessage({ file, documentType: "receipt" });
  }
  function updateComponent(id: string, changes: Partial<Component>) {
    setComponents((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...changes } : row)),
    );
    setPreview(undefined);
  }
  function includeDefaults(row: Component) {
    return Object.keys(row.included).length
      ? row.included
      : Object.fromEntries(activeMembers.map((member) => [member.id, true]));
  }
  function proportionalValues() {
    const weights: Record<string, number> = Object.fromEntries(
      activeMembers.map((member) => [member.id, 0]),
    );
    for (const row of itemComponents) {
      const included = activeMembers.filter(
        (member) => includeDefaults(row)[member.id],
      );
      if (!included.length) continue;
      const amount = Math.abs(Number(row.amount || 0));
      if (row.strategy === "exact")
        included.forEach((member) => {
          weights[member.id] += Number(row.values[member.id] || 0);
        });
      else if (row.strategy === "percentage")
        included.forEach((member) => {
          weights[member.id] +=
            (amount * Number(row.values[member.id] || 0)) / 100;
        });
      else {
        const weightTotal = included.reduce(
            (sum, member) => sum + Number(row.values[member.id] || 1),
            0,
          ),
          unit = amount / weightTotal;
        included.forEach((member) => {
          weights[member.id] += unit * Number(row.values[member.id] || 1);
        });
      }
    }
    return Object.fromEntries(
      Object.entries(weights).map(([id, value]) => [
        id,
        value > 0 ? value.toFixed(6) : "1",
      ]),
    );
  }
  function body() {
    const proportional = proportionalValues(), orderedComponents = [...itemComponents, ...chargeComponents];
    return {
      idempotency_key: idempotencyKey,
      description,
      total,
      currency,
      expense_date: date,
      source_receipt_id:
        receiptRecord?.status === "confirmed" ? receiptRecord.id : null,
      payers: Object.entries(payers)
        .filter(([, amount]) => Number(amount) > 0)
        .map(([member_id, amount]) => ({ member_id, amount })),
      components: orderedComponents.map((row) => {
        const included = includeDefaults(row),
          eligible = activeMembers.filter((member) => included[member.id]);
        const strategy: Strategy =
          row.kind !== "item" && row.policy === "proportional"
            ? "weighted"
            : row.kind !== "item" && row.policy === "custom"
              ? "exact"
              : row.strategy;
        return {
          label: row.label,
          amount: row.amount,
          strategy,
          category_id: row.categoryId || null,
          kind: row.kind,
          non_discountable: Boolean(row.nonDiscountable),
          promotion_id: row.promotionId || null,
          discount_mode: row.kind === "discount" ? row.discountMode ?? "fixed" : null,
          percentage: row.discountMode === "percentage" ? row.percentage || null : null,
          cap: row.kind === "discount" ? row.cap || null : null,
          minimum_order: row.kind === "discount" ? row.minimumOrder || null : null,
          eligible_component_indexes:
            row.kind === "discount"
              ? orderedComponents.flatMap((item, index) =>
                  item.kind === "item" && row.eligibleItemIds?.includes(item.id) ? [index] : [],
                )
              : [],
          shares: eligible.map((member) => ({
            member_id: member.id,
            ...(strategy === "equal"
              ? {}
              : {
                  value:
                    row.kind !== "item" && row.policy === "proportional"
                      ? proportional[member.id]
                      : row.values[member.id],
                }),
          })),
        };
      }),
    };
  }
  async function requestPreview() {
    if (!selected) return false;
    setBusy(true);
    const response = await fetch(
        `${apiUrl}/v1/groups/${selected.id}/expenses/preview`,
        { method: "POST", headers, body: JSON.stringify(body()) },
      ),
      result = await response.json();
    setBusy(false);
    if (!response.ok) {
      setPreview(undefined);
      setStatus(
        typeof result.detail === "string"
          ? result.detail
          : "Correct the highlighted allocation fields.",
      );
      return false;
    }
    setPreview(result);
    setStatus("Every component and participant reconciles exactly.");
    return true;
  }
  async function stageReceipt() {
    if (!file || !extraction || !receipt || !reconciled)
      return setStatus(
        "Correct the receipt until its components match the grand total.",
      );
    setBusy(true);
    const source_hash = [
      ...new Uint8Array(
        await crypto.subtle.digest("SHA-256", await file.arrayBuffer()),
      ),
    ]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    const reviewed: ReceiptCandidate = {
      ...receipt,
      merchant: description,
      document_date: date,
      currency,
      total,
      items: itemComponents.map((row) => ({
        label: row.label,
        quantity: row.quantity,
        unit_price: row.unitPrice,
        line_total: row.amount,
        category_id: row.categoryId,
        evidence:
          row.confidence === undefined
            ? undefined
            : { page: 1, text: row.label, confidence: row.confidence },
      })),
      discount:
        chargeComponents.find((row) => row.kind === "discount")?.amount ??
        "0.00",
      tax: chargeComponents.find((row) => row.kind === "tax")?.amount ?? "0.00",
      service_charge:
        chargeComponents.find((row) => row.kind === "service_charge")?.amount ??
        "0.00",
      delivery_fee:
        chargeComponents.find((row) => row.kind === "delivery")?.amount ?? "0.00",
      packaging_fee:
        chargeComponents.find((row) => row.kind === "packaging")?.amount ?? "0.00",
      tip: chargeComponents.find((row) => row.kind === "tip")?.amount ?? "0.00",
      rounding:
        chargeComponents.find((row) => row.kind === "rounding")?.amount ??
        "0.00",
      issues: [],
    };
    const response = await fetch(`${apiUrl}/v1/receipts`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          idempotency_key: crypto.randomUUID(),
          account_id: null,
          source_hash,
          file_name: file.name,
          source_format: extraction.source_format,
          document_type: "receipt",
          page_count: extraction.pages,
          used_ocr: extraction.used_ocr,
          elapsed_ms: extraction.elapsed_ms,
          candidate: reviewed,
        }),
      }),
      result = await response.json();
    setBusy(false);
    if (!response.ok)
      return setStatus(
        typeof result.detail === "string"
          ? result.detail
          : "The reviewed receipt could not be staged.",
      );
    setReceiptRecord(result);
    setStatus(
      "Receipt reviewed. Optionally select a matching payment, then confirm its provenance.",
    );
  }
  async function confirmReceipt() {
    if (!receiptRecord) return;
    setBusy(true);
    const response = await fetch(
        `${apiUrl}/v1/receipts/${receiptRecord.id}/confirm`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            expected_version: receiptRecord.version,
            linked_transaction_id: linkedId || null,
          }),
        },
      ),
      result = await response.json();
    setBusy(false);
    if (!response.ok)
      return setStatus(
        result.detail ?? "Receipt provenance could not be confirmed.",
      );
    setReceiptRecord(result);
    setStatus(
      linkedId
        ? "Receipt linked to the reviewed bank payment. It will not be counted twice."
        : "Receipt provenance confirmed without a bank match.",
    );
  }
  function validateStep() {
    if (step === 0 && (!description.trim() || !date || Number(total) <= 0))
      return "Enter a description, date, and positive grand total.";
    if (
      step === 1 &&
      (!activeMembers.length ||
        sumMoney(Object.values(payers).filter(Boolean), currency) !==
          sumMoney([total], currency))
    )
      return "Choose participants and make payer contributions equal the bill total.";
    if (
      step === 2 &&
      itemComponents.some(
        (row) =>
          !activeMembers.some((member) => includeDefaults(row)[member.id]),
      )
    )
      return "Assign at least one consumer to every item.";
    if (step === 3 && !reconciled && !hasCalculatedDiscount)
      return "Correct the bill until components equal the grand total.";
    if (step === 3 && extraction && receiptRecord?.status !== "confirmed")
      return "Return to Details and confirm the reviewed receipt provenance.";
    if (
      step === 3 &&
      chargeComponents.some(
        (row) =>
          !activeMembers.some((member) => includeDefaults(row)[member.id]),
      )
    )
      return "Every charge must have at least one eligible participant.";
  }
  async function next() {
    const error = validateStep();
    if (error) return setStatus(error);
    if (step === 3 && !(await requestPreview())) return;
    setStep((value) => Math.min(4, value + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function confirmExpense() {
    if (!selected || !(preview || (await requestPreview()))) return;
    setBusy(true);
    const response = await fetch(
        `${apiUrl}/v1/groups/${selected.id}/expenses`,
        { method: "POST", headers, body: JSON.stringify(body()) },
      ),
      result = await response.json();
    setBusy(false);
    if (!response.ok)
      return setStatus(result.detail ?? "The expense could not be confirmed.");
    router.push(`/groups/${selected.id}/expenses/${result.id}`);
  }
  const money = (value: string) =>
    new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(Number(value));
  const categoryOptions = categories.filter((row) => row.parent_id);

  return (
    <main className="guided-split" id="main-content">
      <header className="builder-header">
        <div>
          <Link
            className="back-link"
            href={selected ? `/groups/${selected.id}` : "/groups"}
          >
            ← Back to group
          </Link>
          <p className="eyebrow">Guided split</p>
          <h1>
            {selected
              ? `Add expense · ${selected.name}`
              : "Add a group expense"}
          </h1>
          <p>
            Receipt processing stays in this browser. Final amounts come from
            the deterministic group ledger.
          </p>
        </div>
        <label className="compact-label">
          Group
          <select
            value={groupId}
            onChange={(event) => selectGroup(event.target.value)}
          >
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
      </header>
      <nav className="builder-steps" aria-label="Expense steps">
        <ol>
          {steps.map((label, index) => (
            <li
              key={label}
              className={index === step ? "active" : index < step ? "done" : ""}
            >
              <button
                type="button"
                onClick={() => index < step && setStep(index)}
                disabled={index > step}
              >
                <span>{index < step ? "✓" : index + 1}</span>
                {label}
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
      {!selected ? (
        <section className="panel empty">
          <h2>No active group</h2>
          <p>Create or restore a group before adding an expense.</p>
          <Link className="button-link" href="/groups">
            Open groups
          </Link>
        </section>
      ) : (
        <div className="builder-layout">
          <section className="panel builder-stage">
            {step === 0 && (
              <>
                <StageTitle
                  number="1"
                  title="Bill details"
                  aside="Manual or local extraction"
                />
                <div className="receipt-drop">
                  <div>
                    <strong>Upload a receipt</strong>
                    <p>PDF, JPG, PNG or WebP · 10 MiB · up to 20 PDF pages</p>
                  </div>
                  <label className="button-link">
                    Choose file
                    <input
                      className="sr-only"
                      type="file"
                      accept="application/pdf,image/jpeg,image/png,image/webp"
                      capture="environment"
                      onChange={chooseFile}
                    />
                  </label>
                  {file && (
                    <button
                      className="secondary"
                      type="button"
                      disabled={busy}
                      onClick={extract}
                    >
                      {busy ? "Reading…" : "Extract locally"}
                    </button>
                  )}
                </div>
                {extraction && (
                  <div
                    className="confidence-note"
                    data-low={receipt && receipt.confidence < 0.7}
                  >
                    <strong>
                      {receipt && receipt.confidence < 0.7
                        ? "Needs careful review"
                        : "Extraction ready"}
                    </strong>
                    <span>
                      {extraction.used_ocr
                        ? "OCR was used"
                        : "PDF text was read directly"}{" "}
                      · {Math.round((receipt?.confidence ?? 0) * 100)}%
                      extraction confidence
                    </span>
                  </div>
                )}
                <div className="form-row">
                  <label>
                    Merchant or description
                    <input
                      value={description}
                      maxLength={280}
                      onChange={(event) => setDescription(event.target.value)}
                    />
                  </label>
                  <label>
                    Date
                    <input
                      type="date"
                      value={date}
                      onChange={(event) => setDate(event.target.value)}
                    />
                  </label>
                </div>
                <div className="form-row">
                  <label>
                    Grand total
                    <input
                      inputMode="decimal"
                      value={total}
                      onChange={(event) => setTotal(event.target.value)}
                    />
                  </label>
                  <label>
                    Currency
                    <select
                      value={currency}
                      onChange={(event) => setCurrency(event.target.value)}
                    >
                      {currencies.map((code) => (
                        <option key={code}>{code}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <div
                  className={
                    reconciled
                      ? "reconcile-banner valid"
                      : "reconcile-banner invalid"
                  }
                >
                  <strong>
                    {reconciled ? "Bill reconciles" : "Correction required"}
                  </strong>
                  <span>
                    Components {money(componentTotal)} · Grand total{" "}
                    {money(total || "0")}
                  </span>
                </div>
                {extraction && (
                  <section className="provenance-card">
                    <h3>Receipt provenance and bank match</h3>
                    {!receiptRecord ? (
                      <button
                        type="button"
                        disabled={busy || !reconciled}
                        onClick={stageReceipt}
                      >
                        Review matching payments
                      </button>
                    ) : receiptRecord.status !== "confirmed" ? (
                      <>
                        <fieldset>
                          <legend>Optional matching transaction</legend>
                          <label className="match-option">
                            <input
                              type="radio"
                              name="match"
                              checked={!linkedId}
                              onChange={() => setLinkedId("")}
                            />{" "}
                            No matching payment
                          </label>
                          {receiptRecord.matches.map((match) => (
                            <label
                              className="match-option"
                              key={match.transaction_id}
                            >
                              <input
                                type="radio"
                                name="match"
                                checked={linkedId === match.transaction_id}
                                onChange={() =>
                                  setLinkedId(match.transaction_id)
                                }
                              />
                              <span>
                                <strong>
                                  {match.description} · {money(match.amount)}
                                </strong>
                                <small>
                                  {match.date} · {match.evidence.join(" · ")}
                                </small>
                              </span>
                            </label>
                          ))}
                        </fieldset>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={confirmReceipt}
                        >
                          Confirm receipt{" "}
                          {linkedId ? "and bank link" : "provenance"}
                        </button>
                      </>
                    ) : (
                      <p className="verified-line">
                        ✓ Reviewed provenance confirmed
                        {receiptRecord.linked_transaction_id
                          ? " and linked without double counting"
                          : ""}
                        .
                      </p>
                    )}
                  </section>
                )}
              </>
            )}
            {step === 1 && (
              <>
                <StageTitle
                  number="2"
                  title="People & payers"
                  aside="Consumption is separate from cash paid"
                />
                <fieldset>
                  <legend>Who took part?</legend>
                  <div className="chip-grid">
                    {selected.members.map((member) => (
                      <label
                        className={
                          participants[member.id]
                            ? "person-chip selected"
                            : "person-chip"
                        }
                        key={member.id}
                      >
                        <input
                          type="checkbox"
                          checked={participants[member.id] ?? false}
                          onChange={(event) =>
                            setParticipants((current) => ({
                              ...current,
                              [member.id]: event.target.checked,
                            }))
                          }
                        />
                        <span>
                          {member.display_name}
                          <small>{member.is_guest ? "Guest" : "Member"}</small>
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                <fieldset>
                  <legend>Who paid the merchant?</legend>
                  <p className="field-help">
                    Enter actual cash contributions. These do not determine
                    consumption.
                  </p>
                  <div className="allocation-grid">
                    {activeMembers.map((member) => (
                      <label key={member.id}>
                        {member.display_name}
                        <input
                          aria-label={`${member.display_name} paid`}
                          inputMode="decimal"
                          value={payers[member.id] ?? ""}
                          onChange={(event) =>
                            setPayers((current) => ({
                              ...current,
                              [member.id]: event.target.value,
                            }))
                          }
                          placeholder="0.00"
                        />
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      activeMembers[0] &&
                      setPayers({ [activeMembers[0].id]: total })
                    }
                  >
                    One person paid the full bill
                  </button>
                </fieldset>
              </>
            )}
            {step === 2 && (
              <>
                <StageTitle
                  number="3"
                  title="Items & splitting"
                  aside={
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        setComponents((rows) => [
                          ...rows,
                          freshComponent("New item"),
                        ])
                      }
                    >
                      Add item
                    </button>
                  }
                />
                <p className="field-help">
                  Preferences are never applied automatically. Select the people
                  who actually consumed each item.
                </p>
                {itemComponents.map((row, index) => (
                  <ItemEditor
                    key={row.id}
                    row={row}
                    index={index}
                    members={activeMembers}
                    categories={categoryOptions}
                    update={updateComponent}
                    remove={() =>
                      setComponents((rows) =>
                        rows.filter((item) => item.id !== row.id),
                      )
                    }
                    defaults={includeDefaults(row)}
                  />
                ))}
              </>
            )}
            {step === 3 && (
              <>
                <StageTitle
                  number="4"
                  title="Taxes & charges"
                  aside={
                    <button
                      type="button"
                      className="secondary"
                      onClick={() =>
                        setComponents((rows) => [
                          ...rows,
                          freshComponent("Tax", "tax"),
                        ])
                      }
                    >
                      Add charge
                    </button>
                  }
                />
                <p className="field-help">
                  Proportional allocation follows each eligible person’s item
                  subtotal. Inclusive taxes remain inside item prices, not here.
                </p>
                {chargeComponents.length ? (
                  chargeComponents.map((row) => (
                    <ChargeEditor
                      key={row.id}
                      row={row}
                      members={activeMembers}
                      items={itemComponents}
                      update={updateComponent}
                      remove={() =>
                        setComponents((rows) =>
                          rows.filter((item) => item.id !== row.id),
                        )
                      }
                      defaults={includeDefaults(row)}
                    />
                  ))
                ) : (
                  <div className="empty compact">
                    <h3>No separate charges</h3>
                    <p>
                      Continue when tax and service are already included in item
                      prices.
                    </p>
                  </div>
                )}
              </>
            )}
            {step === 4 && (
              <>
                <StageTitle
                  number="5"
                  title="Review exact shares"
                  aside="minor-units-v1"
                />
                {preview ? (
                  <>
                    <div className="review-summary">
                      <div>
                        <span>Bill total</span>
                        <strong>{money(total)}</strong>
                      </div>
                      <div>
                        <span>Participants</span>
                        <strong>{activeMembers.length}</strong>
                      </div>
                      <div>
                        <span>Components</span>
                        <strong>{components.length}</strong>
                      </div>
                    </div>
                    <section
                      className="split-preview"
                      aria-label="Exact split preview"
                    >
                      {preview.balances.map((row) => (
                        <div key={row.member_id}>
                          <span>{names.get(row.member_id)}</span>
                          <small>
                            Paid {money(row.paid)} · consumption{" "}
                            {money(row.owed)}
                          </small>
                          <strong
                            className={
                              Number(row.balance) < 0 ? "negative" : ""
                            }
                          >
                            {Number(row.balance) < 0 ? "owes" : "gets back"}{" "}
                            {money(Math.abs(Number(row.balance)).toString())}
                          </strong>
                        </div>
                      ))}
                    </section>
                    <details className="allocation-details">
                      <summary>Show item allocations</summary>
                      {components.map((item) => (
                        <div key={item.id}>
                          <strong>
                            {item.label} · {money(preview.components?.find((row) => row.label === item.label)?.amount ?? item.amount)}
                          </strong>
                          <p>
                            {preview.allocations
                              .filter(
                                (row) => row.component_label === item.label,
                              )
                              .map(
                                (row) =>
                                  `${names.get(row.member_id)} ${money(row.amount)}`,
                              )
                              .join(" · ")}
                          </p>
                        </div>
                      ))}
                    </details>
                    <div className="calculation-order" aria-label="Calculation order">
                      <strong>Calculation order</strong>
                      <ol><li>Recorded item prices and inclusive taxes</li><li>Eligible discounts, in the order shown</li><li>Recorded taxes, service, delivery, packaging, and tips</li><li>Deterministic minor-unit allocation among eligible people</li></ol>
                    </div>
                    <button
                      className="confirm-expense"
                      type="button"
                      disabled={busy}
                      onClick={confirmExpense}
                    >
                      {busy ? "Confirming…" : "Confirm reconciled expense"}
                    </button>
                    <p className="field-help">
                      Confirmation creates an immutable ledger record.
                      Corrections use a separately audited reversal flow.
                    </p>
                  </>
                ) : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={requestPreview}
                  >
                    Calculate exact preview
                  </button>
                )}
              </>
            )}
            <footer className="builder-nav">
              <button
                type="button"
                className="secondary"
                disabled={step === 0 || busy}
                onClick={() => setStep((value) => value - 1)}
              >
                Back
              </button>
              {step < 4 && (
                <button type="button" disabled={busy} onClick={next}>
                  Continue to {steps[step + 1]}
                </button>
              )}
            </footer>
          </section>
          <aside className="panel live-breakdown">
            <p className="eyebrow">Live bill</p>
            <h2>{money(total || "0")}</h2>
            <p>{description || "Untitled expense"}</p>
            <dl>
              <div>
                <dt>Items</dt>
                <dd>
                  {money(
                    sumMoney(itemComponents.map((row) => row.amount || "0"), currency),
                  )}
                </dd>
              </div>
              <div>
                <dt>Adjustments</dt>
                <dd>
                  {money(
                    sumMoney(chargeComponents.map((row) => row.amount || "0"), currency),
                  )}
                </dd>
              </div>
              <div>
                <dt>Participants</dt>
                <dd>{activeMembers.length}</dd>
              </div>
              <div>
                <dt>Paid so far</dt>
                <dd>
                  {money(sumMoney(Object.values(payers).filter(Boolean), currency))}
                </dd>
              </div>
            </dl>
            {!reconciled && !hasCalculatedDiscount && (
              <p className="warning-copy">
                The component total must equal the grand total before
                confirmation.
              </p>
            )}
            {hasCalculatedDiscount && !preview && (
              <p className="field-help">Percentage promotions are calculated and validated by the financial engine during preview.</p>
            )}
          </aside>
        </div>
      )}
    </main>
  );
}

function kindFor(label: string): Kind {
  return /tax|gst|vat/i.test(label)
    ? "tax"
    : /discount/i.test(label)
      ? "discount"
      : /service/i.test(label)
        ? "service_charge"
        : /tip/i.test(label)
          ? "tip"
          : /round/i.test(label)
            ? "rounding"
            : "item";
}
function StageTitle({
  number,
  title,
  aside,
}: {
  number: string;
  title: string;
  aside: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        <p className="eyebrow">Step {number}</p>
        <h2>{title}</h2>
      </div>
      <span>{aside}</span>
    </div>
  );
}
function ItemEditor({
  row,
  index,
  members,
  categories,
  update,
  remove,
  defaults,
}: {
  row: Component;
  index: number;
  members: Member[];
  categories: Category[];
  update: (id: string, changes: Partial<Component>) => void;
  remove: () => void;
  defaults: Record<string, boolean>;
}) {
  return (
    <fieldset className="component guided-component">
      <legend>
        Item {index + 1}
        {row.confidence !== undefined && row.confidence < 0.7
          ? " · verify OCR"
          : ""}
      </legend>
      <div className="component-controls">
        <label>
          Item
          <input
            value={row.label}
            onChange={(event) => update(row.id, { label: event.target.value })}
          />
        </label>
        <label>
          Quantity
          <input
            inputMode="decimal"
            value={row.quantity}
            onChange={(event) =>
              update(row.id, { quantity: event.target.value })
            }
          />
        </label>
        <label>
          Unit price
          <input
            inputMode="decimal"
            value={row.unitPrice}
            onChange={(event) =>
              update(row.id, { unitPrice: event.target.value })
            }
          />
        </label>
        <label>
          Line total
          <input
            inputMode="decimal"
            value={row.amount}
            onChange={(event) => update(row.id, { amount: event.target.value })}
          />
        </label>
        <label>
          Category
          <select
            value={row.categoryId ?? ""}
            onChange={(event) =>
              update(row.id, { categoryId: event.target.value || undefined })
            }
          >
            <option value="">Uncategorized</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Split method
          <select
            value={row.strategy}
            onChange={(event) =>
              update(row.id, { strategy: event.target.value as Strategy })
            }
          >
            <option value="equal">Equal</option>
            <option value="quantity">Custom quantities</option>
            <option value="percentage">Percentages</option>
            <option value="exact">Exact amounts</option>
            <option value="weighted">Weighted</option>
            <option value="usage">Usage</option>
            <option value="time">Time</option>
          </select>
        </label>
      </div>
      <ParticipantSelector
        row={row}
        members={members}
        update={update}
        defaults={defaults}
      />
      <label className="non-discountable-toggle">
        <input type="checkbox" checked={Boolean(row.nonDiscountable)} onChange={(event) => update(row.id, { nonDiscountable: event.target.checked })}/>
        Exclude this item from promotions
      </label>
      <button
        type="button"
        className="text-button danger-text"
        onClick={remove}
      >
        Remove item
      </button>
    </fieldset>
  );
}
function ChargeEditor({
  row,
  members,
  items,
  update,
  remove,
  defaults,
}: {
  row: Component;
  members: Member[];
  items: Component[];
  update: (id: string, changes: Partial<Component>) => void;
  remove: () => void;
  defaults: Record<string, boolean>;
}) {
  return (
    <fieldset className="component guided-component">
      <legend>{row.kind.replaceAll("_", " ")}</legend>
      <div className="component-controls">
        <label>
          Type
          <select value={row.kind} onChange={(event) => update(row.id, { kind: event.target.value as Kind, discountMode: event.target.value === "discount" ? row.discountMode ?? "fixed" : undefined })}>
            <option value="discount">Discount</option><option value="tax">Additional tax</option><option value="service_charge">Service charge</option><option value="delivery">Delivery fee</option><option value="packaging">Packaging fee</option><option value="tip">Tip</option><option value="rounding">Rounding</option>
          </select>
        </label>
        <label>
          Label
          <input
            value={row.label}
            onChange={(event) => update(row.id, { label: event.target.value })}
          />
        </label>
        {row.kind === "discount" && <label>
          Discount method
          <select value={row.discountMode ?? "fixed"} onChange={(event) => update(row.id, { discountMode: event.target.value as Component["discountMode"], amount: event.target.value === "percentage" ? "0" : row.amount })}>
            <option value="fixed">Fixed amount</option><option value="percentage">Percentage</option><option value="cashback">External cashback</option>
          </select>
        </label>}
        {row.kind === "discount" && row.discountMode === "percentage" ? <label>
          Percentage
          <input inputMode="decimal" value={row.percentage ?? ""} onChange={(event) => update(row.id, { percentage: event.target.value })} placeholder="e.g. 20" />
        </label> : <label>
          Amount
          <input
            inputMode="decimal"
            value={row.amount}
            onChange={(event) => update(row.id, { amount: event.target.value })}
          />
        </label>}
        <label>
          Allocation policy
          <select
            value={row.policy}
            onChange={(event) =>
              update(row.id, {
                policy: event.target.value as Component["policy"],
              })
            }
          >
            <option value="proportional">Proportional to items</option>
            <option value="equal">Equal among eligible people</option>
            <option value="custom">Custom exact amounts</option>
          </select>
        </label>
      </div>
      {row.kind === "discount" && <div className="promotion-scope">
        <fieldset><legend>Eligible items</legend>{items.map((item) => <label key={item.id} className={item.nonDiscountable ? "disabled-choice" : ""}><input type="checkbox" disabled={item.nonDiscountable} checked={row.eligibleItemIds?.includes(item.id) ?? false} onChange={(event) => update(row.id, { eligibleItemIds: event.target.checked ? [...(row.eligibleItemIds ?? []), item.id] : (row.eligibleItemIds ?? []).filter((id) => id !== item.id) })}/><span>{item.label}{item.nonDiscountable ? " · excluded" : ""}</span></label>)}</fieldset>
        <label>Promotion reference<input value={row.promotionId ?? ""} onChange={(event) => update(row.id, { promotionId: event.target.value })} placeholder="e.g. SAVE20" autoComplete="off" /></label>
        <label>Maximum discount<input inputMode="decimal" value={row.cap ?? ""} onChange={(event) => update(row.id, { cap: event.target.value })} placeholder="Optional cap" /></label>
        <label>Minimum eligible order<input inputMode="decimal" value={row.minimumOrder ?? ""} onChange={(event) => update(row.id, { minimumOrder: event.target.value })} placeholder="Optional minimum" /></label>
        {row.discountMode === "cashback" && <p className="warning-copy">Cashback is not deducted from this bill. Record it only when it actually arrives.</p>}
      </div>}
      <ParticipantSelector
        row={{ ...row, strategy: row.policy === "custom" ? "exact" : "equal" }}
        members={members}
        update={update}
        defaults={defaults}
      />
      <button
        type="button"
        className="text-button danger-text"
        onClick={remove}
      >
        Remove charge
      </button>
    </fieldset>
  );
}
function ParticipantSelector({
  row,
  members,
  update,
  defaults,
}: {
  row: Component;
  members: Member[];
  update: (id: string, changes: Partial<Component>) => void;
  defaults: Record<string, boolean>;
}) {
  const needsValue = row.strategy !== "equal";
  return (
    <div
      className="participant-selector"
      role="group"
      aria-label={`${row.label} consumers`}
    >
      {members.map((member) => {
        const checked = defaults[member.id] ?? false;
        return (
          <div
            className={
              checked ? "participant-choice selected" : "participant-choice"
            }
            key={member.id}
          >
            <label>
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) =>
                  update(row.id, {
                    included: {
                      ...defaults,
                      [member.id]: event.target.checked,
                    },
                  })
                }
              />
              <span>{member.display_name}</span>
            </label>
            {checked && needsValue && (
              <input
                aria-label={`${member.display_name} ${row.strategy}`}
                inputMode="decimal"
                value={row.values[member.id] ?? ""}
                onChange={(event) =>
                  update(row.id, {
                    values: { ...row.values, [member.id]: event.target.value },
                  })
                }
                placeholder={
                  row.strategy === "percentage"
                    ? "%"
                    : row.strategy === "exact"
                      ? "Amount"
                      : "Weight"
                }
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
