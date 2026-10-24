"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Image from "next/image";

type Report = { id:string; kind:string; description:string|null; steps:string|null; page_path:string|null; viewport:string|null; contact_allowed:boolean; screenshot_data:string|null; created_at:string };

export default function FeedbackReviewPage() {
  const [reports,setReports]=useState<Report[]>([]),[status,setStatus]=useState("Loading private reports…");
  useEffect(()=>{fetch("/api/backend/v1/feedback").then(async response=>{if(!response.ok)throw new Error(response.status===404?"This private review page is not available for your account.":"Reports could not be loaded.");return response.json() as Promise<Report[]>}).then(data=>{setReports(data);setStatus(data.length?"":"No beta reports yet.")}).catch(error=>setStatus(error.message))},[]);
  return <main id="main-content" className="feedback-review"><header><Link href="/settings">← Settings</Link><p className="eyebrow">Developer review</p><h1>Private Beta Reports</h1><p>Reports stay inside the application and are never published as GitHub issues.</p></header><p role="status">{status}</p><div className="feedback-report-list">{reports.map(report=><article className="panel" key={report.id}><header><span>{report.kind.replaceAll("_"," ")}</span><time dateTime={report.created_at}>{new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short"}).format(new Date(report.created_at))}</time></header><p>{report.description}</p>{report.steps&&<details><summary>Steps to reproduce</summary><p>{report.steps}</p></details>}<dl><div><dt>Page</dt><dd>{report.page_path??"Not shared"}</dd></div><div><dt>Viewport</dt><dd>{report.viewport??"Not shared"}</dd></div><div><dt>Contact</dt><dd>{report.contact_allowed?"Allowed":"Not requested"}</dd></div></dl>{report.screenshot_data&&<Image unoptimized src={report.screenshot_data} width={480} height={270} alt="Screenshot explicitly attached to this beta report" loading="lazy"/>}</article>)}</div></main>;
}
