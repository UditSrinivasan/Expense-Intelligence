"use client";

import { ChangeEvent, FormEvent, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Image from "next/image";

const categories = [{value:"bug",label:"Bug report"},{value:"suggestion",label:"Feature suggestion"},{value:"split",label:"Confusing UX"},{value:"calculation",label:"Incorrect financial calculation"},{value:"general",label:"General feedback"}];

async function safeScreenshot(file: File) {
  if (!file.type.startsWith("image/") || file.size > 4_000_000) throw new Error("Choose a PNG or JPEG smaller than 4 MB.");
  const bitmap = await createImageBitmap(file), scale = Math.min(1, 1200 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas"); canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height); bitmap.close();
  return canvas.toDataURL("image/jpeg", .78);
}

export function FeedbackPanel() {
  const pathname = usePathname(), dialog = useRef<HTMLDialogElement>(null);
  const [screenshot, setScreenshot] = useState<string>(), [status, setStatus] = useState(""), [busy, setBusy] = useState(false);
  async function chooseScreenshot(event: ChangeEvent<HTMLInputElement>) { const file=event.target.files?.[0]; if (!file) return setScreenshot(undefined); try { setScreenshot(await safeScreenshot(file)); setStatus("Screenshot selected. Review it before submitting."); } catch(error) { setScreenshot(undefined); setStatus(error instanceof Error ? error.message : "Screenshot could not be prepared."); } }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const formElement=event.currentTarget; setBusy(true); setStatus("Sending…"); const form=new FormData(formElement);
    const response=await fetch("/api/backend/v1/feedback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({kind:form.get("kind"),sentiment:"report",description:form.get("description"),steps:form.get("steps")||null,page_path:form.get("include_context")?pathname:null,viewport:`${window.innerWidth}x${window.innerHeight}`,contact_allowed:Boolean(form.get("contact_allowed")),screenshot_data:screenshot??null})});
    setBusy(false); if(!response.ok){setStatus("Feedback could not be sent. Remove sensitive details and try again.");return;} formElement.reset();setScreenshot(undefined);setStatus("Thank you. Your private beta report was recorded.");
  }
  return <><button type="button" className="feedback-launcher" onClick={() => dialog.current?.showModal()}>Report a Bug / Suggest</button><dialog ref={dialog} className="feedback-dialog" aria-labelledby="feedback-title"><form method="dialog" className="dialog-close"><button aria-label="Close feedback form">×</button></form><form onSubmit={submit}><p className="eyebrow">Private beta</p><h2 id="feedback-title">Report a Bug or Suggest an Improvement</h2><p>Do not include account numbers, transaction details, receipts, tokens, or other private financial information.</p><label>Feedback type<select name="kind" required>{categories.map(category=><option key={category.value} value={category.value}>{category.label}</option>)}</select></label><label>What happened or could improve?<textarea name="description" required maxLength={2000} rows={4} placeholder="Describe the issue without financial details…"/></label><label>Steps to reproduce <span>(optional)</span><textarea name="steps" maxLength={2000} rows={3} placeholder="1. Open…"/></label><label className="check-row"><input type="checkbox" name="include_context" defaultChecked/>Include current page path</label><label className="check-row"><input type="checkbox" name="contact_allowed"/>You may contact me about this report</label><label>Screenshot <span>(optional and explicitly selected)</span><input type="file" accept="image/png,image/jpeg" onChange={chooseScreenshot}/></label>{screenshot&&<Image unoptimized className="feedback-preview" src={screenshot} width={320} height={180} alt="Selected screenshot preview"/>}<button disabled={busy} type="submit">{busy?"Sending…":"Send Private Feedback"}</button><p role="status" aria-live="polite">{status}</p></form></dialog></>;
}
