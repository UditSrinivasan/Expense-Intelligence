"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

type Message = { id: string; role: "user" | "assistant"; content: string; tools?: string[] };
type Thread = { id: string; title: string };
type Flag = { name: string; enabled: boolean };

const apiUrl = "/api/backend";
const headers = { "Content-Type": "application/json" };

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadId, setThreadId] = useState<string>();
  const [flags, setFlags] = useState<Flag[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("Synthetic showcase data only");
  const endRef = useRef<HTMLDivElement>(null);

  async function refreshThreads() {
    const response = await fetch(`${apiUrl}/v1/chat/threads`, { headers });
    if (response.ok) setThreads(await response.json());
  }

  useEffect(() => {
    Promise.all([fetch(`${apiUrl}/v1/flags`, { headers }), fetch(`${apiUrl}/v1/chat/threads`, { headers })])
      .then(async ([flagResponse, threadResponse]) => {
        if (flagResponse.ok) setFlags(await flagResponse.json());
        if (threadResponse.ok) setThreads(await threadResponse.json());
      }).catch(() => setNotice("Start the local API to use the assistant."));
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  async function openThread(id: string) {
    const response = await fetch(`${apiUrl}/v1/chat/threads/${id}/messages`, { headers });
    if (response.ok) { setThreadId(id); setMessages(await response.json()); }
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = new FormData(form).get("message")?.toString().trim();
    if (!input || busy) return;
    const optimistic: Message = { id: crypto.randomUUID(), role: "user", content: input };
    setMessages((current) => [...current, optimistic]);
    form.reset(); setBusy(true); setNotice("Agent is choosing finance tools…");
    try {
      const response = await fetch(`${apiUrl}/v1/agent/chat`, { method: "POST", headers, body: JSON.stringify({ content: input, thread_id: threadId }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Assistant unavailable");
      setThreadId(body.thread_id);
      setMessages((current) => [...current, { ...body.message, tools: body.tools_used }]);
      setNotice(`${body.model} · synthetic fixture · ${body.tools_used.length} tool${body.tools_used.length === 1 ? "" : "s"}`);
      await refreshThreads();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Assistant unavailable"); }
    finally { setBusy(false); }
  }

  const flag = (name: string) => flags.find((item) => item.name === name)?.enabled ?? false;
  return <main className="assistant-shell" id="main-content">
    <header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link><div className="environment"><i aria-hidden="true" /> Synthetic agent lab</div></header>
    <section className="assistant-grid">
      <aside className="conversation-rail" aria-label="Conversation history">
        <div><p className="eyebrow">Conversations</p><h1>Finance assistant</h1><p className="rail-copy">A bounded Gemini agent with auditable, read-only tools.</p></div>
        <button className="secondary" onClick={() => { setThreadId(undefined); setMessages([]); }}>+ New conversation</button>
        <nav>{threads.map((thread) => <button className={thread.id === threadId ? "thread active" : "thread"} key={thread.id} onClick={() => openThread(thread.id)}>{thread.title}</button>)}</nav>
        <div className="memory-panel"><p className="eyebrow">Memory strategy</p><span>{flag("CHAT_HISTORY") ? "●" : "○"} Chat history</span><span>{flag("SHORT_TERM_MEMORY") ? "●" : "○"} Short term</span><span>{flag("LONG_TERM_MEMORY") ? "●" : "○"} Long term</span></div>
      </aside>
      <section className="chat-panel" aria-label="Finance assistant chat">
        <div className="chat-context"><div><span className="mode-chip">Synthetic data</span><strong>October 2026 showcase ledger</strong></div><p role="status">{notice}</p></div>
        <div className="messages" aria-live="polite">
          {!messages.length && <div className="welcome"><span>✦</span><h2>Ask a question grounded in the ledger.</h2><p>Try a monthly comparison, category breakdown, transaction search, or INR–GBP conversion.</p><div className="prompts"><button onClick={() => setNotice("Type this below: Compare September and October spending")}>Compare two months</button><button onClick={() => setNotice("Type this below: Break down October by category")}>Category breakdown</button></div></div>}
          {messages.map((message) => <article className={`message ${message.role}`} key={message.id}><small>{message.role === "user" ? "You" : "Expense Intelligence"}</small><ReactMarkdown>{message.content}</ReactMarkdown>{message.tools?.length ? <div className="tool-row">{message.tools.map((tool) => <span key={tool}>✓ {tool.replaceAll("_", " ")}</span>)}</div> : null}</article>)}
          {busy && <div className="thinking"><i /><i /><i /> Running a bounded tool workflow</div>}<div ref={endRef} />
        </div>
        <form className="composer" onSubmit={send}><label htmlFor="message">Message</label><textarea id="message" name="message" maxLength={4000} required placeholder="Ask about the synthetic showcase ledger…" /><button disabled={busy} type="submit">{busy ? "Working…" : "Send"}</button><small>Read-only tools · No transfers or account actions · Synthetic demo data</small></form>
      </section>
    </section>
  </main>;
}
