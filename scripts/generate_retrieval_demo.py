#!/usr/bin/env python3
"""Generate an original fictional query PDF for a curated retrieval demonstration."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "frontend/public/samples/retrieval-demo-anticipatory-bail.pdf"
)

PAGES = [
    ("Anticipatory Bail After a Village Dispute", [
        ("Hypothetical criminal application | Patna High Court | 2023", [
            "Fictional applicants: Aman Prakash and Kunal Prakash. Proposed respondent: "
            "State of Bihar. Research question: anticipatory bail under Section 438 of "
            "the Code of Criminal Procedure, 1973 (CrPC), following allegations under "
            "Sections 341, 323, 324, 307, 504, 506 and 34 of the Indian Penal Code, 1860 "
            "(IPC). This is an invented pre-hearing case brief, not a filed application "
            "or a court judgment. No decision or entitlement to bail is asserted.",
        ]),
        ("Facts and procedural posture", [
            "In May 2023, a quarrel allegedly occurred near an irrigation channel in a "
            "fictional Bihar village after a dispute about access to adjoining fields. "
            "The informant names several relatives as participants, alleges that one "
            "person struck him with an iron implement, and alleges that others blocked "
            "his path, shouted threats and joined the assault. A group assault and "
            "common intention are alleged; these assertions have not been proved.",
            "The FIR attributes the alleged implement blow to a separately named "
            "co-accused. As to Aman and Kunal, the description is collective and does "
            "not identify an individual weapon, blow or injury. The applicants dispute "
            "participation and allege false implication arising from a continuing land "
            "dispute. The State says the FIR must be considered as a whole and that "
            "the investigation may establish coordinated participation.",
            "The supplied medical summary describes swelling and superficial injuries "
            "as simple, with no fracture recorded. The prosecution disputes whether "
            "that summary resolves the seriousness of the alleged attack or intention. "
            "Simple injuries alone are not assumed to exclude Section 307 IPC.",
        ]),
        ("Competing submissions on pre-arrest bail", [
            "The applicants seek protection from arrest, offer to cooperate with the "
            "investigation and undertake not to contact witnesses. They rely on the "
            "absence of a specific overt act attributed to them, the disputed group "
            "allegation, simple injuries and a claimed lack of criminal antecedents. "
            "They mention a counter-complaint and parity with a co-accused, but copies "
            "and the precise role comparison remain to be verified.",
            "The State opposes anticipatory bail because the alleged offences are "
            "serious, witnesses live nearby and the applicants' roles require inquiry. "
            "It asks the court to consider intimidation risk and whether custodial "
            "interrogation is needed. No automatic grant or rejection is requested in "
            "this research brief; the issue is how comparable courts assessed these factors.",
        ]),
    ]),
    ("Issues for Comparable-Case Research", [
        ("What the retrieval should help investigate", [
            "Find comparable High Court decisions on Section 438 CrPC applications "
            "where an assault FIR includes Section 307 IPC but the medical account "
            "records simple injuries. Compare the factual role of each applicant, "
            "rather than matching the offence number alone.",
            "Examine how courts distinguish general or omnibus allegations from a "
            "specific overt act; whether a weapon allegation concerns the applicant "
            "or another accused; and how Section 34 IPC affects the inquiry without "
            "treating lack of a specific blow as automatic exoneration.",
            "Compare clean-antecedent claims, case and counter-case situations, "
            "cooperation with investigation, alleged witness threats, custodial "
            "interrogation and genuinely similarly situated co-accused. Identify "
            "material differences as well as shared facts.",
            "Review the conditions imposed in any comparable pre-arrest bail order, "
            "including cooperation, appearance and non-interference with witnesses. "
            "Do not treat an earlier bail order as a guarantee for these applicants.",
        ]),
        ("Record limitations", [
            "No original FIR, medical report, counter-complaint, witness statement, "
            "case diary or previous bail order is attached. The facts above are "
            "invented inputs for a software demonstration. All disputed matters "
            "require independent verification. No actual person's legal position is assessed.",
        ]),
        ("Historical legal setting", [
            "The scenario is deliberately set in 2023 and uses IPC/CrPC terminology "
            "for comparison with historical judgments. It is not guidance on current "
            "BNS/BNSS provisions or on transitional application to a real case.",
        ]),
    ]),
]


def generate_pdf(output: Path = OUTPUT) -> Path:
    """Write a reproducible, selectable-text A4 brief without network requests."""
    output.parent.mkdir(parents=True, exist_ok=True)
    ink = colors.HexColor("#173a43")
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, leading=14,
                          spaceAfter=10, textColor=colors.HexColor("#27343b"))
    heading = ParagraphStyle("Heading", fontName="Helvetica-Bold", fontSize=11,
                             leading=15, spaceBefore=8, spaceAfter=7, textColor=ink)
    title = ParagraphStyle("Title", fontName="Times-Bold", fontSize=25, leading=29,
                           spaceAfter=16, textColor=ink)
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=48,
                                 leftMargin=48, topMargin=75, bottomMargin=70,
                                 title="Fictional Anticipatory Bail Research Brief",
                                 author="NyayaAI", invariant=1)
    story = []
    for index, (page_title, sections) in enumerate(PAGES):
        if index:
            story.append(PageBreak())
        story.append(Paragraph(escape(page_title), title))
        for section_title, paragraphs in sections:
            story.append(Paragraph(escape(section_title), heading))
            for paragraph in paragraphs:
                story.append(Paragraph(escape(paragraph), body))
        story.append(Spacer(1, 4))

    def page_frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ink)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(48, A4[1] - 42, "NYAYA AI / FICTIONAL RESEARCH BRIEF")
        canvas.setStrokeColor(colors.HexColor("#cbd5d8"))
        canvas.line(48, 53, A4[0] - 48, 53)
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.drawString(48, 39, "FICTIONAL FACTS / NOT A REAL JUDGMENT / NOT LEGAL ADVICE")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(48, 27, "No outcome determined. Historical IPC/CrPC setting: 2023.")
        canvas.drawRightString(A4[0] - 48, 27, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output


if __name__ == "__main__":
    generate_pdf()
