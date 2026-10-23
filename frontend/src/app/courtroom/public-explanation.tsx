import { BookOpen, Check, CircleAlert } from "lucide-react";
import type { CourtroomPublicExplanation } from "@/lib/api/types";

export function PublicExplanation({ explanation, onInspectSource }: {
  explanation?: CourtroomPublicExplanation | null;
  onInspectSource: () => void;
}) {
  if (!explanation) return <p className="explanation-unavailable"><CircleAlert size={16} />Structured explanation not available for this submission. Do not treat the report as an evidence-verified conclusion.</p>;

  return <section className="public-explanation" aria-label="Why this conclusion">
    <div className="explanation-heading"><BookOpen size={17} /><h3>Why this conclusion</h3><span>Public explanation</span></div>
    <p className="conclusion-basis">{explanation.conclusion_basis}</p>
    <div className="evidence-records"><h4>Evidence used</h4>
      {explanation.supporting_evidence.length === 0 ? <p>No supporting source excerpts supplied by this agent.</p> : explanation.supporting_evidence.map((evidence, index) => <article key={index} className="evidence-record">
        <div className="evidence-reference"><strong>{evidence.source_ref}</strong><span data-verified={evidence.quote_verified}>{evidence.quote_verified ? <Check size={13} /> : <CircleAlert size={13} />}{evidence.quote_verified ? "Quote matched source text" : "Quote not verified"}</span></div>
        <blockquote>{evidence.quote}</blockquote><p><strong>Why it matters: </strong>{evidence.relevance}</p>
        {evidence.source_ref === "case_text" ? <a href="#case-source-record" onClick={onInspectSource}>Inspect case record</a> : <p className="evidence-origin">{evidence.quote_verified ? "Matched to a supplied legal excerpt. Verify the original authority separately." : "No supplied source was matched to this quotation."}</p>}
      </article>)}
    </div>
    <div className="explanation-grid">{[
      { title: "Assumptions, not established facts", items: explanation.assumptions },
      { title: "Counterarguments considered", items: explanation.counterarguments },
      { title: "Uncertainty and missing information", items: explanation.uncertainty },
    ].map(({ title, items }) => <div key={title}><h4>{title}</h4>{items.length ? <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>None identified by this agent. This does not establish that none exist.</p>}</div>)}</div>
    {explanation.change_summary && <div className="position-change"><h4>Why the position changed or stayed the same</h4><p>{explanation.change_summary}</p></div>}
    <p className="explanation-caveat">These are model-generated explanations, not a transcript of internal thinking. A matched quotation establishes only that the words appear in supplied source text, not that the evidence is true, complete, or legally sufficient.</p>
  </section>;
}
