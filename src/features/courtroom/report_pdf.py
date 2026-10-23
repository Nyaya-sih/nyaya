"""Paginated public courtroom reports generated from canonical server snapshots."""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

from src.features.courtroom.schemas import CourtroomAnalysisResponse


def build_report_pdf(report: CourtroomAnalysisResponse) -> bytes:
    """Render canonical public fields without requests or model calls."""
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font_path.is_file():
        font_path = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    font_name = "CourtroomDejaVu" if "DejaVu" in font_path.name else "CourtroomVera"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    glyphs = pdfmetrics.getFont(font_name).face.charToGlyph
    styles = {
        "body": ParagraphStyle(
            "ReportBody", fontName=font_name, fontSize=9, leading=14,
            spaceAfter=7, splitLongWords=True,
        ),
        "title": ParagraphStyle(
            "ReportTitle", fontName=font_name, fontSize=25, leading=31,
            spaceAfter=16, textColor=colors.HexColor("#153b45"),
        ),
        "section": ParagraphStyle(
            "ReportSection", fontName=font_name, fontSize=14, leading=19,
            spaceBefore=16, spaceAfter=10, keepWithNext=True,
            textColor=colors.HexColor("#153b45"),
        ),
        "label": ParagraphStyle(
            "ReportLabel", fontName=font_name, fontSize=9, leading=14,
            spaceBefore=5, spaceAfter=3, keepWithNext=True,
            textColor=colors.HexColor("#52636a"),
        ),
    }
    story = []

    def text(value: object, style: str = "body") -> None:
        raw = str(value)
        # Unsupported text stays recoverable via explicit Unicode code points.
        safe = "".join(
            char if (char in "\n\t" or (ord(char) >= 32 and ord(char) in glyphs))
            else f"[U+{ord(char):04X}]" for char in raw
        )
        # Bounded flowables keep very large excerpts splittable across pages.
        for line in safe.split("\n"):
            while line:
                end = len(line)
                if end > 2400:
                    end = line.rfind(" ", 0, 2400) + 1 or 2400
                chunk, line = line[:end], line[end:]
                story.append(Paragraph(escape(chunk) or "&#160;", styles[style]))

    def fields(value: object, label: str = "") -> None:
        if label:
            text(label.replace("_", " ").capitalize(), "label")
        if value is None or value == [] or value == {} or value == "":
            text("Unavailable / not supplied in this snapshot.")
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "quote_verified":
                    text("Evidence match: " + (
                        "Matched supplied source text (not independent truth verification)."
                        if item is True else "NOT VERIFIED against supplied source text."
                    ))
                else:
                    fields(item, key)
        elif isinstance(value, list):
            for index, item in enumerate(value, 1):
                fields(item, f"Item {index}")
        else:
            text(value)

    roles = report.initial_role_analyses + report.role_analyses
    approved = (
        report.status == "completed"
        and report.judge_review is not None
        and report.judge_review.approved is True
        and not report.judge_review.required_changes
        and not report.judge_review.degraded
        and report.synthesis is not None
        and not report.synthesis.degraded
        and not any(role.degraded for role in roles)
    )
    if report.status in {"queued", "running"}:
        banner = "INCOMPLETE / NOT APPROVED"
    else:
        banner = "SIMULATED JUDGE APPROVED" if approved else "NOT APPROVED"
    text("NyayaAI", "label")
    text("Courtroom Analysis Report", "title")
    text(banner, "section")
    text(f"Run status: {report.status} | Mode: {report.mode}")
    text(f"Canonical analysis ID: {report.analysis_id}")
    text(f"Created: {report.created_at.isoformat()}")
    completed = report.completed_at.isoformat() if report.completed_at else "Unavailable / not completed"
    text(f"Completed: {completed}")
    text(report.disclaimer)
    text(
        "Decision support only. This is a simulated review, not a court judgment, "
        "legal advice, or an independently verified finding."
    )
    text(
        "Same-model warning: multiple roles may use the same underlying model. "
        "Agreement and peer scores are not independent corroboration. Confidence "
        "values are model self-assessments, not calibrated probabilities."
    )
    text(
        "Snapshot scope: only canonical public outputs available at download time "
        "are included. No private model thinking is exposed or inferred. Original "
        "case text is not included in this report; a generated case summary is not "
        "the original source. Source evidence below contains only the supplied "
        "excerpts, not necessarily complete source documents."
    )
    text(
        f"Font: {font_path.name}. Unsupported glyphs and control characters are "
        "shown as [U+XXXX] markers; consult the canonical JSON for exact original "
        "text. No shaping of complex scripts is guaranteed."
    )
    data = report.model_dump(mode="json")
    sections = [
        ("Synthesis and Areas of Agreement", "synthesis"),
        ("Judicial Review", "judge_review"),
        ("Original Role Analyses", "initial_role_analyses"),
        ("Rebuttal / Final Role Analyses", "role_analyses"),
        ("Rebuttal Enabled", "rebuttal_enabled"),
        ("Rebuttal Changes", "rebuttal_changes"),
        ("Warnings", "warnings"),
        ("Peer Assessments", "evaluation_breakdown"),
        ("Transparency and Diagnostics", "transparency_dashboard"),
        ("Audit Event Log", "trial_events"),
    ]
    for title, key in sections:
        text(title, "section")
        if key == "role_analyses":
            text(
                "Final role outputs; when rebuttal is disabled these may repeat "
                "the original analyses. Missing results remain unavailable, "
                "including in running snapshots."
            )
        fields(data[key])
    text("End of canonical public snapshot. No supplied sections or excerpts were intentionally truncated.")
    output = BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=48, leftMargin=48,
        topMargin=52, bottomMargin=52, title="NyayaAI Courtroom Analysis Report",
        author="NyayaAI", pageCompression=1,
    )

    def page_frame(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5d8"))
        canvas.line(48, 40, A4[0] - 48, 40)
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor("#52636a"))
        canvas.drawString(48, 27, f"NyayaAI | {banner} | Not legal advice")
        canvas.drawRightString(A4[0] - 48, 27, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()
