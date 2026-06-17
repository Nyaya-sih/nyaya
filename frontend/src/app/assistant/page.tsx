"use client";

import { useEffect, useState } from "react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { useAssistantQuery, useCreateAssistantSession } from "@/lib/hooks/use-assistant";

export default function AssistantPage() {
  const [sessionId, setSessionId] = useState<string>("");
  const [question, setQuestion] = useState("");

  const createSession = useCreateAssistantSession();
  const query = useAssistantQuery();

  useEffect(() => {
    if (sessionId) return;
    createSession.mutate(undefined, {
      onSuccess: (res) => setSessionId(res.session_id),
    });
  }, [createSession, sessionId]);

  const handleAsk = () => {
    if (!sessionId || question.trim().length < 5) return;
    query.mutate({
      session_id: sessionId,
      question: question.trim(),
      top_k: 8,
      include_history: true,
    });
  };

  return (
    <div>
      <PageHeader
        title="Legal Assistant"
        breadcrumb={[{ label: "Home", href: "/" }, { label: "Assistant" }]}
        description="Ask legal research questions with citation-backed responses."
      />
      <Container className="space-y-6 pb-16">
        <div className="legal-panel p-5">
          <p className="text-xs text-[var(--neutral-500)]">Session</p>
          <p className="mt-1 text-sm text-[var(--neutral-700)]">
            {sessionId || "Creating session..."}
          </p>
        </div>

        <div className="legal-panel p-5">
          <label className="mb-2 block text-sm font-medium text-[var(--neutral-700)]">
            Question
          </label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="min-h-[120px] w-full rounded-xl border border-[var(--border)] p-3 text-sm"
            placeholder="E.g., What are the bail conditions under BNSS?"
          />
          <button
            type="button"
            onClick={handleAsk}
            disabled={!sessionId || query.isPending || question.trim().length < 5}
            className="legal-button-primary mt-3 px-5 py-2 text-sm font-semibold disabled:opacity-60"
          >
            {query.isPending ? "Thinking..." : "Ask Assistant"}
          </button>
        </div>

        {query.data && (
          <div className="space-y-4">
            <div className="legal-panel p-5">
              <p className="text-xs text-[var(--neutral-500)]">Answer</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--neutral-800)]">
                {query.data.answer_text}
              </p>
              <p className="mt-3 text-xs text-[var(--neutral-500)]">{query.data.disclaimer}</p>
            </div>

            <div className="legal-panel p-5">
              <p className="text-xs text-[var(--neutral-500)]">Citations</p>
              <ul className="mt-2 space-y-2 text-sm text-[var(--neutral-800)]">
                {query.data.citations.map((c) => (
                  <li key={c.citation_id}>
                    {c.citation_id} - {c.act_or_case} {c.section_or_article ? `(${c.section_or_article})` : ""} - score {c.score.toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </Container>
    </div>
  );
}
