"use client";

import { useState } from "react";
import { ArrowLeft, BookOpen, Gavel, HeartHandshake, Landmark, Scale, Shield } from "lucide-react";
import type { CourtroomAnalysisResponse, CourtroomRoleAnalysis, CourtroomTrialEvent } from "@/lib/api/types";
import { PublicExplanation } from "./public-explanation";

export interface AgentInspectorProps {
  roleName: string;
  label: string;
  mandate: string;
  events: CourtroomTrialEvent[];
  initialAnalysis?: CourtroomRoleAnalysis;
  currentAnalysis?: CourtroomRoleAnalysis;
  judgeReview?: NonNullable<CourtroomAnalysisResponse["judge_review"]> | null;
  running: boolean;
  onClose: () => void;
  onInspectSource: () => void;
}

export function AgentInspector({ roleName, label, mandate, events, initialAnalysis, currentAnalysis, judgeReview, running, onClose, onInspectSource }: AgentInspectorProps) {
  const isJudge = roleName === "Presiding Judge";
  const [stage, setStage] = useState<"position" | "rebuttal" | "vote">(isJudge ? "vote" : "position");
  const stageEvents = events.filter((event) => stage === "vote"
    ? event.event_type === "vote"
    : stage === "position"
      ? event.event_type === "position"
      : event.event_type === "rebuttal" || event.event_type === "revision");
  const event = stageEvents.at(-1);
  // A final role report without an initial snapshot has no reliable round label.
  const revisedSnapshot = Boolean(initialAnalysis && currentAnalysis && (
    initialAnalysis.analysis_text !== currentAnalysis.analysis_text
    || JSON.stringify(initialAnalysis.public_explanation) !== JSON.stringify(currentAnalysis.public_explanation)
  ));
  const snapshot = stage === "position" ? initialAnalysis ?? (!revisedSnapshot && !events.some((item) => item.event_type === "rebuttal" || item.event_type === "revision") ? currentAnalysis : undefined)
    : stage === "rebuttal" && revisedSnapshot ? currentAnalysis : undefined;
  const review = isJudge ? judgeReview : null;
  const content = stage === "vote" ? review?.reasoning ?? event?.content : event?.content ?? snapshot?.analysis_text;
  const explanation = stage === "vote" ? review?.public_explanation ?? event?.public_explanation : event?.public_explanation ?? snapshot?.public_explanation;
  const confidence = stage === "vote" ? review?.confidence ?? event?.confidence : event?.confidence ?? snapshot?.confidence;
  const provider = stage === "vote" ? review?.provider ?? event?.model_provider : event?.model_provider ?? snapshot?.provider;
  const model = stage === "vote" ? review?.model ?? event?.model_id : event?.model_id ?? snapshot?.model;
  const degraded = (stage === "vote" ? review?.degraded : snapshot?.degraded) || provider === "fallback";
  const evidence = (stage === "position" ? initialAnalysis ?? snapshot : stage === "rebuttal" ? currentAnalysis ?? initialAnalysis : undefined)?.source_evidence ?? [];
  const citations = snapshot?.citations ?? [];
  const Icon = isJudge ? Gavel : roleName === "Defense Counsel" ? Shield : roleName === "Constitutional Expert" ? Landmark : roleName === "Moral Advisor" ? HeartHandshake : roleName === "Prosecution Counsel" ? Scale : BookOpen;
  const preview = content?.split(/\n\s*\n/)[0];

  return <aside id="agent-report" className="agent-inspector" aria-label="Agent insight">
    <header className="inspector-header">
      <button type="button" className="inspector-back" onClick={onClose}><ArrowLeft size={16} aria-hidden="true" />Back to case dossier</button>
      <div className="inspector-role-icon"><Icon size={24} strokeWidth={1.5} aria-hidden="true" /></div>
      <p className="courtroom-eyebrow">PARTICIPANT INSIGHT</p>
      <h2 id="agent-inspector-title">{label}</h2>
      <p className="inspector-mandate">{mandate}</p>
    </header>

    <div className="inspector-stages" role="group" aria-label="Submission stage">
      {(isJudge ? [{ value: "vote" as const, title: "Judicial review" }] : [
        { value: "position" as const, title: "Independent opinion" },
        { value: "rebuttal" as const, title: "Shared rebuttal" },
      ]).map((item) => <button key={item.value} type="button" className="inspector-stage" data-selected={stage === item.value} aria-pressed={stage === item.value} aria-controls="inspector-submission" onClick={() => setStage(item.value)}>{item.title}</button>)}
    </div>

    <div className="inspector-body" id="inspector-submission">
      <section className="inspector-sources" aria-label="Information received">
        <h3>Information received</h3>
        <p>{stage === "position" ? "Submitted case record and role-specific legal excerpts. Initial opinions are prepared without seeing peer opinions."
          : stage === "rebuttal" ? "Submitted case record and the same shared snapshot of first-round opinions supplied to every role. This is not a sequence of replies to other rebuttals."
            : "Submitted case record, initial opinions, rebuttals, and the draft conclusion for judicial review."}</p>
        <p>These are workflow boundaries, not a complete prompt transcript. The submitted record is a fixed snapshot; later dossier edits are not included.</p>
        <button type="button" className="inspector-source-link" onClick={onInspectSource}><BookOpen size={14} aria-hidden="true" />Inspect submitted case record</button>
      </section>

      {content ? <>
        <section className="inspector-conclusion" aria-label={isJudge ? "Review outcome" : "Submission overview"}>
          <h3>{isJudge ? "Review outcome" : "Submission overview"}</h3>
          {isJudge && review ? <p><strong>{degraded ? "Review unavailable / fallback" : review.approved ? "Draft summary approved in this simulation" : "Changes required"}</strong></p> : <p>{preview && preview.length > 420 ? `${preview.slice(0, 420)}…` : preview}</p>}
          {!isJudge && <small>Opening excerpt from the submission, not a separately verified finding.</small>}
          {degraded && <p className="explanation-unavailable">Fallback or degraded output. Substantive review is needed; this is not a verified opinion.</p>}
        </section>

        <PublicExplanation explanation={explanation} onInspectSource={onInspectSource} />

        {explanation && <ul className="inspector-coverage" aria-label="Public explanation coverage">
          <li>{explanation.supporting_evidence.length} evidence excerpts</li>
          <li>{explanation.supporting_evidence.filter((item) => item.quote_verified).length} text-matched quotes</li>
          <li>{explanation.assumptions.length} assumptions</li>
          <li>{explanation.counterarguments.length} counterarguments</li>
          <li>{explanation.uncertainty.length} uncertainty notes</li>
        </ul>}

        {stage === "rebuttal" && explanation && !explanation.change_summary && <p className="explanation-unavailable">No explicit explanation of what changed or stayed the same was supplied.</p>}

        {isJudge && <section className="inspector-judge-reasons"><h3>Judge&apos;s public reasons</h3><p className="submission-text">{content}</p>
          {review && <><h4>Required changes</h4>{review.required_changes.length ? <ul>{review.required_changes.map((change, index) => <li key={index}>{change}</li>)}</ul> : <p>No required changes were recorded. This is not independent legal validation.</p>}</>}
        </section>}

        {!isJudge && <details className="inspector-full-report"><summary>Read full submission</summary><p className="submission-text" style={{ whiteSpace: "pre-wrap" }}>{content}</p></details>}

        <div className="inspector-meta">
          <p>{provider || model ? `Model: ${[provider, model].filter(Boolean).join(" / ")}` : "Model identity not recorded for this submission."}</p>
          {typeof confidence === "number" && Number.isFinite(confidence) && <p>Self-reported model confidence: {Math.round(confidence * 100)}%. Uncalibrated; not a probability of legal success or correctness.</p>}
          {event ? <p>Recorded event: <code>{event.event_id}</code>{event.timestamp && <> / <time dateTime={event.timestamp}>{event.timestamp}</time></>}{event.responding_to && <> / Responding to <code>{event.responding_to}</code></>}</p>
            : <p>Shown from the stored report snapshot. No event timestamp is available.{stage === "position" && !initialAnalysis ? " The original round cannot be confirmed from this snapshot alone." : ""}</p>}
        </div>
      </> : <div className="inspector-empty" role="status"><BookOpen size={24} aria-hidden="true" /><h3>{running ? "Awaiting this submission" : "No submission recorded"}</h3><p>{running ? "The agent's public explanation will appear when a report is available. Activity is not a transcript of internal thinking." : "No report is available for this stage. No conclusion, reasons, or evidence have been inferred."}</p></div>}

      <details className="inspector-sources"><summary>Source excerpts and cited references ({evidence.length + (event?.citations.length ?? citations.length)})</summary>
        <p>Server-supplied legal excerpt previews may be shortened. Inclusion does not establish that the agent relied on an excerpt, or that the authority is current or applicable. Excerpts are not the original source document.</p>
        {evidence.length ? evidence.map((block, index) => <article className="evidence-record" key={index}>
          {Object.entries(block).map(([key, value]) => key === "excerpt" || key === "quoted_text" ? <blockquote key={key}>{value}</blockquote> : <p key={key}><strong>{key.replaceAll("_", " ")}: </strong>{value}</p>)}
        </article>) : <p>No server-supplied legal excerpts are attached to this stage&apos;s available report. This does not prove that none were supplied to the model.</p>}
        {event?.citations.length ? event.citations.map((citation, index) => <article key={index} className="evidence-record"><strong>{citation.section_ref}</strong><p>Source: {citation.doc_id}</p>{citation.quoted_text && <blockquote>{citation.quoted_text}</blockquote>}<p>Agent-cited reference; verify against the original authority.</p></article>) : citations.length ? <ul>{citations.map((citation, index) => <li key={index}>{citation}</li>)}</ul> : <p>No cited references recorded for this submission.</p>}
      </details>

      <details className="inspector-activity"><summary>Recorded activity ({events.length})</summary>
        <p>Actual server events only. Status messages describe work, not private internal reasoning.</p>
        {events.length ? <ol>{events.map((item) => <li key={item.event_id}><strong>{item.event_type === "frame" ? "Activity update" : item.event_type} / Round {item.round}</strong>{item.timestamp && <time dateTime={item.timestamp}>{item.timestamp}</time>}<p>{item.event_type === "frame" ? item.content : "Submission recorded. Read its stage above or inspect the hearing transcript."}</p><small>{item.model_provider} / {item.model_id}</small></li>)}</ol> : <p>No activity events available. Stored reports, when present, remain readable above.</p>}
      </details>
      <p className="inspector-disclaimer">Public, model-generated explanations only, not private chain-of-thought. Shared-model role agreement is not independent expert validation. Research and education, not legal advice or a court ruling.</p>
    </div>
  </aside>;
}
