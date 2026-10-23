# NyayaAI Design System

## 0. Design Read
An operational legal research workspace, preserving the existing Tailwind/Radix
component language. The courtroom is a spatial view of a real workflow, not a
chat interface or a theatrical prediction of a court decision.

## 1. Atmosphere & Identity
Ivory paper, navy ink, serif legal headings, and restrained orange accents.
The signature courtroom places a raised judge's bench above opposing counsel
and advisory seats for constitutional, ethical, and neutral legal perspectives.
The chamber is a compact architectural scene: a central raised judge's bench,
opposing counsel desks, an advisory table, timber floor lines, and gallery rails.
Six tactile, softly irregular avatars act as the actual selection controls.
The experience is spatial and modern, not a grid of cards or a fake game.
Live activity is meaningful, never simulated.

## 2. Color
Use the existing globals.css tokens: background, surface, surface-alt, border,
foreground, primary-50 through primary-950, accent-50 through accent-900,
neutral-50 through neutral-900, success, warning, danger, info.
Courtroom dark stage uses primary-950, primary-900 and primary-800; its text uses
primary-50 and primary-200. Active seats use accent-300; completed seats use
primary-200. Paper and text follow semantic tokens so theme changes stay usable.
Do not encode success by color alone: use icons and explicit state labels.
Room material tokens: light wall #e6ebe8, floor #d4dcd7, ink #243d42;
dark wall #13272d, floor #102027, ink #dce9e5. Timber #836448 with
highlight #b59a73; brass #c9ab79. Avatar colors are categorical role identifiers,
not status: judge #c8a15b, prosecution #d58365, defense #7899c2,
constitutional #78a99a, moral #b6a3c2, legal #a4b6ba. Matched/active states
still require explicit text. These localized materials do not replace app tokens.

## 3. Typography
Existing Manrope body, Cormorant Garamond headings, JetBrains Mono metadata.
Body sizes 14/16/18px; metadata 12px; headings 20/24/32/48px. Text reports use
1.7 line height and preserve paragraphs. Never render model output as HTML.

## 4. Spacing & Layout
4px base spacing, using 8/12/16/20/24/32px intervals. Existing Container maximum
width remains. Desktop workspace: courtroom and a 380px dossier/inspector column;
transcript below. Below 1024px stack panels. The chamber remains a spatial floor
plan on mobile, with compact labels and comfortably sized avatar buttons. Agent
selection scrolls to its inspector only on compact layouts. Controls wrap,
reports have no horizontal overflow. Panels use existing 18px rounding.

## 5. Primitives & States
- Existing legal-panel, legal-button-primary, legal-button-secondary remain.
- AgentSeat: a sculpted blob avatar with face, role glyph, name and state label;
  default idle, active reviewing, report ready, rebutting, awaiting judge,
  completed, cancelled, failed. Selected seat has an accent rim; keyboard focus
  has a visible outline. Whole seat is a button and opens an adjacent inspector.
- AgentInspector: named role and mandate, independent/rebuttal stage buttons,
  conclusion, structured public reasons, full report, source excerpts, confidence
  limitations and recorded activity. Accessible by mouse, touch and keyboard.
- ReportExport: PDF from canonical server data with busy/error states; audit
  JSON retains the locally submitted source snapshot. Running PDF exports are
  clearly incomplete, never masquerading as a completed approved hearing.
- HearingStep: numbered phase with pending/active/complete state and text.
- TranscriptEntry: role, event kind, timestamp, provider/model, public report,
  citations, causal link. Empty, live, reconnecting, and terminal are explicit.
- CaseIntake: labeled text input, file input, progress, extraction error,
  disabled while submitting/running, minimum 60 and maximum 120000 characters.
  Connection failures identify the configured API address and recovery action;
  they must not be presented as PDF extraction failures. A failed upload keeps
  the existing draft and allows retrying the same file.
- JudgeDecision: approval is shown only for an explicit successful review;
  unavailable/rejected/degraded outcomes never look like approved decisions.
- PublicExplanation: a visible conclusion basis, quoted evidence with a source
  reference and server-computed text-match label, assumptions, counterarguments,
  uncertainty, and changed/retained position. Missing explanations are explicit.
  Quote matching verifies text presence, never truth or legal correctness.
- SourceRecord: inspectable extracted input with page markers and extraction
  metadata, plus visible extraction/context limits. The submitted snapshot is
  distinct from subsequent draft edits. Native disclosure controls show the
  full record; the JSON audit export includes the submitted text and report.
- SampleDownload: a standard download link to a clearly fictional Indian input
  PDF. Downloads do not start a hearing or send case data to a model.

## 6. Motion & Accessibility
GSAP ScrollTrigger reveals the chamber once with a short transform/opacity
stagger; avatar selection and hover provide tactile feedback. Avatar breathing
is allowed only while that role has actual active-work events, never as fake
thinking. Hover eyes and focus rings are feedback, not work indicators.
Honor prefers-reduced-motion and an explicit Pause motion control. No fake
typing, timed stage progression, or fabricated thinking. Polite live region
announces phase changes; transcript is readable without forced auto-scroll.
All actions have names and visible focus, and expanded reports use native
details/summary. Public explanations are not private chain-of-thought.

## 7. Accepted Debt
Retain existing global frontend styling and font delivery. Run storage is
process-local; a backend restart loses the hearing. Reports are generated by
one model with role-separated calls, not independent expert verification.
