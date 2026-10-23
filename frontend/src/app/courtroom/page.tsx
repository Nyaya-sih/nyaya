"use client";

import { useRef, useState, type ChangeEvent } from "react";
import { ArrowDownToLine, ArrowUpRight, BookOpen, Check, ChevronRight, Download, FileText, Gavel, LoaderCircle, Shield, Square, Upload } from "lucide-react";
import { Container } from "@/components/layout/container";
import { useCancelCourtroomAnalysis, useCourtroomAnalysis, useCourtroomStatus, useCreateCourtroomAnalysis } from "@/lib/hooks/use-courtroom";
import { useCourtroomEvents } from "@/lib/hooks/use-courtroom-events";
import { extractCourtroomDocument, getCourtroomReportPdf } from "@/lib/api/courtroom";
import { API_BASE_URL, ApiError } from "@/lib/api/client";
import type { CourtroomDocument, CourtroomTrialEvent } from "@/lib/api/types";
import { PublicExplanation } from "./public-explanation";
import { AgentInspector } from "./agent-inspector";
import { CourtroomScene, COURTROOM_ROLES } from "./courtroom-scene";
import "./courtroom.css";

const PHASES = ["Case intake", "Independent opinions", "Shared rebuttals", "Draft conclusion", "Judge review"];
const SAMPLE = "A shopkeeper is accused of theft of a mobile phone from a neighbouring store. The complainant identifies the accused from low-resolution CCTV footage, but no stolen property was recovered. The accused says they were at work and offers attendance records and a colleague as an alibi witness. The police recorded statements from two witnesses, whose accounts differ on the time of the incident. The case document does not specify the date of the alleged offence, the applicable statutory provisions, or whether the original CCTV recording has been preserved. Assess the evidentiary gaps and competing positions without assuming guilt.";

function phaseFor(stage: string, events: CourtroomTrialEvent[]) {
  if (events.some((event) => event.event_type === "vote") || stage === "judge_review") return 4;
  if (stage === "synthesis" || events.some((event) => event.event_type === "synthesis")) return 3;
  if (stage === "rebuttal" || stage === "second_evaluation" || events.some((event) => event.stage === "rebuttal")) return 2;
  if (stage === "role_analysis" || stage === "cross_evaluation" || events.some((event) => event.stage === "group_deliberation")) return 1;
  return 0;
}

export default function CourtroomPage() {
  const [caseText, setCaseText] = useState("");
  const [analysisId, setAnalysisId] = useState("");
  const [selectedRole, setSelectedRole] = useState("Prosecution Counsel");
  const [documentName, setDocumentName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [inputError, setInputError] = useState("");
  const [documentInfo, setDocumentInfo] = useState<CourtroomDocument | null>(null);
  const [submittedRecord, setSubmittedRecord] = useState<{ id: string; text: string; filename: string; extraction: CourtroomDocument | null } | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const sidebar = useRef<HTMLDivElement>(null);
  const create = useCreateCourtroomAnalysis();
  const cancel = useCancelCourtroomAnalysis();
  const status = useCourtroomStatus(analysisId);
  const analysis = useCourtroomAnalysis(analysisId);
  const runStatus = status.data?.status ?? analysis.data?.status;
  const missing = [status.error, analysis.error].some((error) => error instanceof ApiError && error.status === 404);
  const running = Boolean(analysisId) && !missing && (!runStatus || runStatus === "queued" || runStatus === "running");
  const busy = running || create.isPending || uploading;
  const stream = useCourtroomEvents(analysisId, running);
  const eventMap = new Map<string, CourtroomTrialEvent>();
  for (const event of [...stream.events, ...(analysis.data?.trial_events ?? [])]) eventMap.set(event.event_id, event);
  const events = [...eventMap.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const phase = phaseFor(status.data?.stage ?? "", events);
  const terminal = Boolean(runStatus) && !running;
  const selectedEvents = events.filter((event) => event.role === selectedRole);
  const report = analysis.data;
  const review = report?.judge_review;
  const warnings = [...new Set([...(create.data?.analysis_id === analysisId ? create.data.warnings : []), ...(status.data?.warnings ?? []), ...(report?.warnings ?? [])])];
  const sourceText = submittedRecord?.id === analysisId ? submittedRecord.text : caseText.trim();
  const sourceInfo = submittedRecord?.id === analysisId ? submittedRecord.extraction : documentInfo;
  const sourceName = submittedRecord?.id === analysisId ? submittedRecord.filename : documentName;
  const selected = COURTROOM_ROLES.find((role) => role.name === selectedRole)!;

  function selectAgent(role: string) {
    setSelectedRole(role);
    setInspectorOpen(true);
    if (window.matchMedia("(max-width: 1023px)").matches) {
      requestAnimationFrame(() => sidebar.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" }));
    }
  }

  function inspectSource() {
    setSourceOpen(true);
    requestAnimationFrame(() => document.getElementById("case-source-record")?.scrollIntoView({ behavior: "instant", block: "start" }));
  }

  async function uploadDocument(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setInputError("Choose a document smaller than 10 MB."); return; }
    setUploading(true);
    setInputError("");
    try {
      const result = await extractCourtroomDocument(file);
      setCaseText(result.text);
      setDocumentName(result.filename);
      setDocumentInfo(result);
      setSourceOpen(true);
    } catch (error) {
      let detail = "Could not read this document. Use a readable PDF, DOCX, or UTF-8 text file (up to 10 MB). Scanned PDFs need OCR first.";
      if (error instanceof TypeError) {
        detail = `Cannot connect to the API at ${API_BASE_URL}. Start the backend, check that this address is reachable from your browser and allowed by CORS, then select the PDF again. Your existing case text has been preserved.`;
      } else if (error instanceof ApiError) {
        try {
          const payload = JSON.parse(error.message);
          if (typeof payload.detail === "string") detail = payload.detail;
        } catch { /* Use the readable fallback for non-JSON proxy errors. */ }
      }
      setInputError(detail);
    } finally { setUploading(false); }
  }

  function startHearing() {
    setInputError("");
    create.mutate({ mode: "quick", include_rebuttal: true, source_type: "text", case_text: caseText, top_k_legal: 8, top_k_cases: 0 }, {
      onSuccess: (result) => {
        setAnalysisId(result.analysis_id);
        setSelectedRole("Prosecution Counsel");
        setInspectorOpen(false);
        setExportError("");
        setSubmittedRecord({ id: result.analysis_id, text: caseText.trim(), filename: documentName, extraction: documentInfo });
      },
    });
  }

  function downloadAudit() {
    if (!report) return;
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), submitted_record: submittedRecord, report }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${analysisId}-audit.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function downloadPdf() {
    if (!analysisId || exporting) return;
    setExporting(true);
    setExportError("");
    try {
      const blob = await getCourtroomReportPdf(analysisId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${analysisId}-courtroom-report.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error instanceof ApiError && error.status === 404
        ? "This hearing is no longer on the server. The PDF cannot be exported."
        : `Could not export the PDF. Check the API connection at ${API_BASE_URL} and try again.`);
    } finally { setExporting(false); }
  }

  return (
    <Container className="courtroom-workspace pb-16 pt-8">
      <header className="courtroom-heading">
        <div><p className="courtroom-eyebrow">A NEW PERSPECTIVE ON LEGAL REASONING</p><h1>Let every side be heard.</h1><p>Your case. Six perspectives. Every public reason, on the record.</p></div>
        <div className="courtroom-heading-actions"><span className="courtroom-mode">Six distinct roles<span>One OpenAI model / Separate prompts</span></span><button type="button" className="report-pdf-button" disabled={!report || missing || exporting} onClick={downloadPdf} title={running ? "Export an explicitly incomplete snapshot of this hearing" : "Download the hearing's public explanations and judicial review"}>{exporting ? <LoaderCircle size={16} className="hearing-spinner" /> : <ArrowDownToLine size={16} />}{exporting ? "Preparing PDF..." : "Export report PDF"}</button></div>
      </header>

      <div className="courtroom-notice"><Shield size={18} /><p><strong>Simulation, not a legal ruling.</strong> Agents show public explanations, evidence, and disagreements, not private internal reasoning. Role agreement is not independent expert validation.</p></div>
      {exportError && <p className="hearing-error" role="alert">{exportError}</p>}

      <ol className="hearing-steps" aria-label="Hearing progress">
        {PHASES.map((label, index) => <li key={label} data-state={analysisId && (index < phase || terminal && index === phase && phase === 4) ? "complete" : running && index === phase ? "active" : "pending"} aria-current={running && index === phase ? "step" : undefined}><span>{analysisId && (index < phase || terminal && index === phase && phase === 4) ? <Check size={14} /> : index + 1}</span><span>{label}</span>{index < 4 && <ChevronRight size={14} className="step-arrow" />}</li>)}
      </ol>

      <div className="courtroom-columns">
        <div className="chamber-column"><CourtroomScene events={events} running={running} terminal={terminal} missing={missing} selectedRole={selectedRole} inspectorOpen={inspectorOpen} report={report} onSelect={selectAgent} />
          <div className="chamber-context"><div><BookOpen size={18} /><span><strong>A seat for every perspective.</strong> Select an agent to inspect its evidence and public reasons.</span></div><button type="button" onClick={() => { setInspectorOpen(false); sidebar.current?.scrollIntoView({ behavior: "instant", block: "start" }); }}>Open case dossier<ArrowUpRight size={14} /></button></div>
        </div>

        <div ref={sidebar} className="courtroom-sidebar">
        {inspectorOpen ? <AgentInspector key={selectedRole} roleName={selectedRole} label={selected.label} mandate={selected.mandate} events={selectedEvents} initialAnalysis={report?.initial_role_analyses.find((item) => item.role_name === selectedRole)} currentAnalysis={report?.role_analyses.find((item) => item.role_name === selectedRole)} judgeReview={review} running={running} onClose={() => setInspectorOpen(false)} onInspectSource={inspectSource} /> : <aside className="case-dossier">
          <div className="dossier-title"><FileText size={19} /><h2>Case dossier</h2></div>
          <p>Every agent receives the same case. Their initial opinions remain independent until the rebuttal round.</p>
          <label className="document-upload" data-disabled={busy}><Upload size={20} /><strong>{uploading ? "Extracting the case record..." : "Upload your case PDF"}</strong><span>PDF, DOCX, TXT / up to 10 MB</span><input type="file" accept=".pdf,.docx,.txt" onChange={uploadDocument} disabled={busy} aria-label="Attach a case document" /></label>
          <a className="sample-pdf-download" href="/samples/indian-theft-case.pdf" download><Download size={16} /><span>Download sample Indian case PDF<small>Fictional theft case / Maharashtra</small></span></a>
          {documentName && <p className="attached-document"><Check size={14} />{documentName}</p>}
          {documentInfo && <div className="extraction-meta" role="status"><p>{documentInfo.page_count != null ? `${documentInfo.page_count} PDF pages / ` : ""}{(documentInfo.extracted_characters ?? documentInfo.text.length).toLocaleString()} characters extracted</p>{documentInfo.warnings?.map((warning, index) => <p key={index} className="extraction-warning">{warning}</p>)}</div>}
          <label htmlFor="case-facts" className="case-text-label">Or enter the facts and legal issues</label>
          <textarea id="case-facts" value={caseText} maxLength={120000} disabled={busy} onChange={(event) => { setCaseText(event.target.value); setDocumentName(""); setDocumentInfo(null); }} placeholder="Include the allegations, evidence, arguments, and procedural history. Do not include unnecessary personal data." />
          <div className="case-text-meta"><span>{caseText.length.toLocaleString()} / 120,000</span><button type="button" disabled={busy} onClick={() => { setCaseText(SAMPLE); setDocumentName("Example case (fictional)"); setDocumentInfo(null); }}>Use example case</button></div>
          {caseText.length > 25000 && <p className="extraction-warning">Only the first 25,000 characters will be reviewed by the agents. Inspect the source record below and shorten the case before starting if needed.</p>}
          <p className="dossier-help">At least 60 characters. Documents are sent to the configured OpenAI API for analysis. Redact sensitive details first.</p>
          {(inputError || create.error) && <p role="alert" className="hearing-error">{inputError || "Could not start the hearing. Check the backend connection and try again."}</p>}
          <button type="button" className="legal-button-primary start-hearing" disabled={busy || caseText.trim().length < 60} onClick={startHearing}>{create.isPending ? <LoaderCircle size={17} className="hearing-spinner" /> : <Gavel size={17} />}{create.isPending ? "Opening hearing..." : running ? "Hearing in progress" : analysisId ? "Start a new hearing" : "Convene the courtroom"}</button>
          {running && <button type="button" className="stop-hearing" disabled={cancel.isPending} onClick={() => cancel.mutate(analysisId, { onSuccess: () => { void status.refetch(); void analysis.refetch(); } })}><Square size={13} />{cancel.isPending ? "Stopping..." : "Stop hearing"}</button>}
          {cancel.error && <p role="alert" className="hearing-error">Unable to cancel. Please retry.</p>}
        </aside>}
        </div>
      </div>

      <div className="hearing-status" role="status" aria-live="polite"><span>{missing ? "Session unavailable" : analysisId ? `${runStatus ?? "Connecting"} / ${PHASES[phase]}` : "Ready when you are. Upload a case to begin."}</span>{analysisId && <span>{status.data?.progress_percent ?? 0}%{running ? stream.isConnected ? " / live connection" : " / refreshing live log" : " / session ended"}</span>}</div>
      {(status.error || analysis.error || stream.error) && <p className="hearing-error" role="alert">{missing ? "This hearing is no longer on the server, possibly after a restart. Your case text is preserved. Start a new hearing to continue." : stream.error || "Unable to refresh this hearing. Check the backend connection; the workspace will retry."}</p>}

      <section className="transparency-protocol" aria-label="How this hearing is explained"><div><BookOpen size={20} /><h2>Follow the evidence, not just the answer.</h2></div><p>Each submission separates its conclusion, supporting quotations, assumptions, counterarguments, and uncertainty. Rebuttals explain what changed or stayed the same. The judge provides separate reasons for approval or rejection.</p><details><summary>What is visible, and what is not?</summary><p>Activity indicators show when work starts and ends; they are not a live transcript of internal thinking. Public explanations are model-generated summaries and may be incomplete. Quote matching checks whether words occur in supplied sources, not whether the claim is true. Confidence and peer scores are model assessments, not calibrated probabilities or independent validation.</p><p>Initial agents receive the case record and role-specific legal excerpts without peer opinions. During rebuttals they receive the same first-round opinion snapshot. The judge receives the case, original opinions, rebuttals, and draft summary. Source extraction warnings and all available reports are included in the audit export.</p></details></section>

      {sourceText && <details id="case-source-record" className="case-source-record" open={sourceOpen} onToggle={(event) => setSourceOpen(event.currentTarget.open)}><summary><FileText size={18} /><span>{submittedRecord?.id === analysisId ? "Inspect submitted case record" : "Inspect extracted case record"}<small>{sourceName || "Pasted case text"}{sourceInfo?.page_count != null ? ` / ${sourceInfo.page_count} pages` : ""} / {sourceText.length.toLocaleString()} characters</small></span><ChevronRight size={16} /></summary><div className="source-record-content"><p>{sourceText.length > 25000 ? "The agents receive only the first 25,000 characters below. Material after the cutoff is excluded." : "This is the extracted text supplied as case context, not the original PDF layout. Check it for extraction errors before relying on the hearing."}</p>{submittedRecord?.id === analysisId && caseText !== sourceText && <p className="extraction-warning">Your edited draft differs from this hearing&apos;s submitted record. Start a new hearing to analyze the changes.</p>}{sourceInfo?.warnings?.map((warning, index) => <p key={index} className="extraction-warning">{warning}</p>)}<pre>{sourceText.slice(0, 25000)}</pre>{sourceText.length > 25000 && <><strong className="context-cutoff">Model context ends here. The following text was not reviewed.</strong><pre className="excluded-source">{sourceText.slice(25000)}</pre></>}</div></details>}

      {report?.synthesis && <section className="judge-summary"><div className="section-heading"><div><p className="courtroom-eyebrow">THE CONCLUSION</p><h2>{review?.approved && !review.degraded ? "Summary approved by the judge" : review?.degraded ? "Draft only. Judicial approval unavailable." : review ? "Judge requests changes" : "Draft submitted for judicial review"}</h2></div><Gavel size={26} /></div><p className="summary-text">{report.synthesis.executive_summary}</p><p className="summary-outcome">{report.synthesis.recommended_outcome}</p>{review && <div className="judge-review"><strong>Judge&apos;s public review</strong><p>{review.reasoning}</p>{review.required_changes.length > 0 && <ul>{review.required_changes.map((item, index) => <li key={index}>{item}</li>)}</ul>}<PublicExplanation explanation={review.public_explanation} onInspectSource={() => setSourceOpen(true)} /></div>}{report.synthesis.unresolved_issues.filter(Boolean).length > 0 && <details><summary>Unresolved issues</summary><ul>{report.synthesis.unresolved_issues.filter(Boolean).map((item, index) => <li key={index}>{item}</li>)}</ul></details>}</section>}

      {report && report.evaluation_breakdown.length > 0 && <details className="peer-assessments"><summary>Inspect peer assessments ({report.evaluation_breakdown.length})</summary><p>These scores are generated by the same model in different roles. They are subjective assessments, not independent expert verification.</p>{report.evaluation_breakdown.map((item, index) => <article key={index}><strong>{item.evaluator_role} assessed {item.target_role}</strong><span>{item.weighted_score.toFixed(1)} / 100</span><p>{item.justification}</p></article>)}</details>}

      <section className="hearing-transcript"><div className="section-heading"><div><h2>Hearing transcript</h2><p>{events.length} recorded events / public submissions only</p></div><button type="button" className="audit-download" disabled={!report} onClick={downloadAudit}><Download size={15} />Export audit JSON</button></div>{events.length === 0 ? <p className="transcript-placeholder">The record will open with case intake. Each opinion, shared rebuttal, and judge review will be logged as it happens.</p> : <div className="transcript-list">{events.map((event, index) => <details key={event.event_id} className="transcript-entry"><summary><span className="transcript-number">{String(index + 1).padStart(2, "0")}</span><span className="transcript-who"><strong>{event.role}</strong><span>{event.event_type === "frame" ? "Activity update" : event.event_type} / Round {event.round}</span></span><time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time><ChevronRight size={16} /></summary><div className="transcript-content"><p>{event.content}</p>{event.responding_to && <p className="transcript-link">Responding to event {events.findIndex((item) => item.event_id === event.responding_to) + 1}</p>}<span>{event.model_provider} / {event.model_id}</span>{event.public_explanation && <PublicExplanation explanation={event.public_explanation} onInspectSource={inspectSource} />}</div></details>)}</div>}</section>

      {warnings.length > 0 && <section className="hearing-warnings" role="note"><h2>Run limitations</h2><ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></section>}
      <p className="courtroom-footnote">Research and education only. All roles use the same model with separate prompts. A simulated judge approval is not legal validation. Hearings are stored temporarily and may be lost if the server restarts.</p>
    </Container>
  );
}
