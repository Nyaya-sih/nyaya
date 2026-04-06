"""Answer generation scaffold for legal assistant."""


class AnswerGenerator:
    """Deterministic answer generator for iteration 0/1.

    Iteration 4 will integrate model-backed generation with strict citation grounding.
    """

    def generate(self, question: str, built_context: str, has_context: bool) -> str:
        """Generate answer text from question and context scaffold."""
        if not has_context:
            return (
                "I do not yet have sufficient contextual material in this session to answer "
                "reliably. Please upload the case document or set context from an existing "
                "case, and I will provide a citation-backed response."
            )

        return (
            "Based on the currently attached session context, the issue appears legally "
            "relevant and requires statute-specific analysis against the case facts. "
            "I have provided grounded excerpts below and recommend verifying the cited "
            "provisions and precedents before relying on this as litigation strategy."
        )
