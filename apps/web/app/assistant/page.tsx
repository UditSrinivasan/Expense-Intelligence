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
  const [messages, setMessages] = useState<Message[]>([]), [threads, setThreads] = useState<Thread[]>([]), [threadId, setThreadId] = useState<string>(), [flags, setFlags] = useState<Flag[]>([]);
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState("External model access is disabled. Synthetic showcase mode only."), [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  async function refreshThreads() { const response = await fetch(`${apiUrl}/v1/chat/threads`, { headers }); if (response.ok) { const body = await response.json(); setThreads(Array.isArray(body) ? body : []); } }
  useEffect(() => { Promise.all([fetch(`${apiUrl}/v1/flags`, { headers }), fetch(`${apiUrl}/v1/chat/threads`, { headers })]).then(async ([flagResponse, threadResponse]) => {
    if (flagResponse.ok) { const body = await flagResponse.json(); setFlags(Array.isArray(body) ? body : []); }
    if (threadResponse.ok) { const body = await threadResponse.json(); setThreads(Array.isArray(body) ? body : []); }
  }).catch(() => setError("Start the local API to use the assistant.")); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);
  async function openThread(id: string) { const response = await fetch(`${apiUrl}/v1/chat/threads/${id}/messages`, { headers }); if (response.ok) { const body = await response.json(); setThreadId(id); setMessages(Array.isArray(body) ? body : []); setError(""); } }
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const input = new FormData(form).get("message")?.toString().trim(); if (!input || busy) return;
    setMessages(current => [...current, { id: crypto.randomUUID(), role: "user", content: input }]); form.reset(); setBusy(true); setError(""); setNotice("Checking the bounded synthetic tool workflow…");
    try { const response = await fetch(`${apiUrl}/v1/agent/chat`, { method: "POST", headers, body: JSON.stringify({ content: input, thread_id: threadId }) }); const body = await response.json(); if (!response.ok) throw new Error(body.detail ?? "Assistant unavailable"); setThreadId(body.thread_id); setMessages(current => [...current, { ...body.message, tools: body.tools_used }]); setNotice(`${body.model} · synthetic fixture · ${body.tools_used.length} read-only tool${body.tools_used.length === 1 ? "" : "s"}`); await refreshThreads(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Assistant unavailable"); setNotice("No answer was added and no financial action was taken."); } finally { setBusy(false); }
  }
  const flag = (name: string) => flags.find(item => item.name === name)?.enabled ?? false;
  return <main className="assistant-shell" id="main-content"><header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link><div className="environment"><i aria-hidden="true"/> Synthetic agent lab</div></header><section className="assistant-grid">
    <aside className="conversation-rail" aria-label="Conversation history"><div><p className="eyebrow">Conversations</p><h1>Finance assistant</h1><p className="rail-copy">A bounded, provider-neutral interface with auditable read-only tools.</p></div><button className="secondary" onClick={() => { setThreadId(undefined); setMessages([]); setError(""); setNotice("New conversation ready. Synthetic showcase mode only."); }}>+ New conversation</button><nav aria-label="Saved conversations">{threads.length ? threads.map(thread => <button className={thread.id === threadId ? "thread active" : "thread"} key={thread.id} onClick={() => openThread(thread.id)}>{thread.title}</button>) : <p className="rail-copy">No saved conversations yet.</p>}</nav><div className="memory-panel"><p className="eyebrow">Memory controls</p><span>{flag("CHAT_HISTORY") ? "●" : "○"} Chat history</span><span>{flag("SHORT_TERM_MEMORY") ? "●" : "○"} Conversation context</span><span>{flag("LONG_TERM_MEMORY") ? "●" : "○"} Long-term demo preferences</span><small>Independent, server-controlled switches. Disabled memory is not silently retained.</small><Link href="/settings">Privacy & account settings</Link></div></aside>
    <section className="chat-panel" aria-label="Finance assistant chat"><div className="chat-context"><div><span className="mode-chip">Synthetic · disconnected</span><strong>October 2026 showcase ledger</strong><small>No private records or mutation tools are connected.</small></div><p role="status">{notice}</p></div>{error ? <div className="assistant-error" role="alert"><strong>Assistant unavailable</strong><p>{error}</p><p>Try again later or use dashboard evidence links. Requests are not retried automatically.</p></div> : null}<div className="messages" aria-live="polite">
      {!messages.length && <div className="welcome"><span>✦</span><h2>Ask about the synthetic ledger.</h2><p>Finance answers should cite tool activity. General questions may not need a finance tool, but this disabled lab will not contact an external model.</p><div className="prompts"><button onClick={() => setNotice("Try: Compare September and October spending")}>Compare two months</button><button onClick={() => setNotice("Try: Break down October by category")}>Category breakdown</button></div></div>}
      {messages.map(message => <article className={`message ${message.role}`} key={message.id}><small>{message.role === "user" ? "You" : "Expense Intelligence"}</small><ReactMarkdown>{message.content}</ReactMarkdown>{message.tools?.length ? <details className="tool-evidence"><summary>{message.tools.length} read-only tool{message.tools.length === 1 ? "" : "s"} used · View evidence trail</summary><div className="tool-row">{message.tools.map(tool => <span key={tool}>✓ {tool.replaceAll("_", " ")}</span>)}</div><p>Generated from synthetic tool results. Tool output is treated as untrusted content.</p></details> : null}{message.role === "assistant" ? <ResponseFeedback messageId={message.id}/> : null}</article>)}{busy && <div className="thinking" role="status"><i/><i/><i/> Running a bounded tool workflow</div>}<div ref={endRef}/></div>
      <form className="composer" onSubmit={send}><label htmlFor="message">Message</label><textarea id="message" name="message" maxLength={4000} required placeholder="Ask about the synthetic showcase ledger…"/><button disabled={busy} type="submit">{busy ? "Working…" : "Send"}</button><small>Read-only tools · No transfers or account actions · Synthetic demo data</small></form></section>
  </section></main>;
}

function ResponseFeedback({ messageId }: { messageId: string }) {
  const [status, setStatus] = useState("");
  async function send(sentiment: "helpful" | "unhelpful") { const response = await fetch(`${apiUrl}/v1/feedback`, { method: "POST", headers, body: JSON.stringify({ kind: "assistant", sentiment, target_id: messageId, reason: sentiment === "unhelpful" ? "wrong_result" : undefined }) }); setStatus(response.ok ? "Feedback recorded. This does not automatically retrain a model." : "Feedback could not be recorded."); }
  return <div className="response-feedback" aria-label="Rate this response"><span>Was this useful?</span><button onClick={() => void send("helpful")}>Helpful</button><button onClick={() => void send("unhelpful")}>Unhelpful</button><small role="status">{status}</small></div>;
}
