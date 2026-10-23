#!/usr/bin/env python3
"""Generate the fictional courtroom sample using only the Python standard library.

Run from any directory: python scripts/generate_courtroom_sample.py
The PDF uses selectable Base-14 text, fixed A4 pages, and deterministic bytes.
No external assets, credentials, network access, or PDF packages are required.
"""

from pathlib import Path
import textwrap


OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "frontend/public/samples/indian-theft-case.pdf"
)

PAGES = [
    (
        "The Alleged Incident",
        "01 / FACTS & TIMELINE",
        [
            ("Case Record | Not a Judgment", [
                "Hypothetical State of Maharashtra v Arjun Mehta. Fictional forum: "
                "Judicial Magistrate First Class, Pune. Exercise ID: DEMO-THEFT-2023. "
                "No real case number, filed charge, hearing, or judicial finding is represented.",
                "All persons, businesses, records, quotations and events below are invented "
                "for this exercise. Any resemblance is coincidental. This is a source packet "
                "for adversarial analysis, not an outcome or an authentic police/court record.",
            ]),
            ("01 | Facts and Allegations", [
                "The scenario concerns an alleged shop theft on 15 March 2023 at the "
                "fictional Nira Mobile Corner, Pune. Shopkeeper Kavya Rao alleges that a "
                "display phone worth INR 18,500 disappeared during an evening visit by "
                "Arjun Mehta [E1]. Ownership, value, taking and identity remain unproved.",
                "Arjun denies taking any phone and claims he attended an evening training "
                "session at fictional Westbridge Skills Centre [E4]. No phone is recorded "
                "as recovered in the supplied exercise inventory [E7]. That inventory does "
                "not establish what occurred outside this packet.",
                "Record facts are limited: E1-E7 are the supplied fictional materials; "
                "they contain conflicting accounts. A statement's inclusion is not proof "
                "that its contents are true. No witness credibility has been determined.",
            ]),
            ("02 | Timeline / All Times Local (IST)", [
                "15 March, 17:55 - [E4] lists a handwritten sign-in beside Arjun's name. "
                "There is no sign-out entry or continuous-presence record.",
                "18:08-18:12 - [E2] clip overlay shows a customer near the shop counter. "
                "Clock accuracy is unknown; overlay time is not established actual time.",
                "About 18:10 - [E1] alleges a phone was taken. [E3] places a similar-looking "
                "person outside around 18:20; [E5] instead describes departure before 18:00.",
                "18:25 - [E4] instructor note records a roll call but not each person's "
                "arrival/departure. Travel time between shop and centre is not supplied.",
                "16 March - [E6] says an officer received a USB copy from the shopkeeper. "
                "18 March - [E7] lists no recovered handset. These are packet dates only.",
            ]),
            ("Reading Key", [
                "[E1]-[E7] are stable source references used throughout. Quotation marks "
                "identify invented excerpts from this packet, not real testimony or law. "
                "Use the exhibit and its limitations together when making an argument.",
            ]),
        ],
    ),
    (
        "Evidence Register",
        "02 / EXHIBITS & LIMITATIONS",
        [
            ("03 | Evidence / Fictional Excerpts", [
                "The excerpts below are the complete evidence supplied for the exercise. "
                "There are no attached originals, actual video files, sworn depositions, "
                "or authenticated records. Do not infer that an omitted document exists.",
            ]),
            ("[E1] Shopkeeper Complaint Summary | 15 March 2023", [
                'Kavya Rao: "At about 6:10 pm I saw Arjun put the display phone into his '
                'bag. I turned to the cash drawer and he was gone. I had not sold it." '
                "Limitation: allegation only; no stock ledger, receipt, device identifier "
                "or account of uninterrupted observation is supplied.",
            ]),
            ("[E2] CCTV Viewing Note | Clip Overlay 18:08-18:12", [
                'Unsigned note: "A person in a dark jacket reaches toward the display. '
                'The face is partly obscured. The object in the hand cannot be resolved." '
                "Limitation: this describes a clip, not an identification result. No "
                "original recording, full sequence or verified clock offset is supplied.",
            ]),
            ("[E3] Nearby Vendor Statement | 16 March 2023", [
                'Fictional vendor Dev Shah: "I think it was Arjun outside at about 6:20. '
                'I recognised the jacket, but I did not see anyone take a phone." '
                "Limitation: uncertain identity, approximate time and no direct account "
                "of a taking; prior familiarity and viewing conditions are undocumented.",
            ]),
            ("[E4] Attendance Sheet and Instructor Note | 15 March 2023", [
                'Sheet: "Arjun Mehta - 17:55" (handwritten). Fictional instructor Mira '
                'Sen: "His name was marked present at the 18:25 roll call. I cannot say '
                'he stayed in the room throughout." Limitation: authorship of sign-in, '
                "method of roll call and original sheet are unverified; no exit log.",
            ]),
            ("[E5] Shop Assistant Statement | 17 March 2023", [
                'Fictional assistant Rohan Kale: "The customer in the dark jacket left '
                'before 6 pm. I noticed the empty stand after 6:15. I did not see a taking." '
                "Limitation: this conflicts with E1's timing and direct-observation claim. "
                "Whether both describe the same customer or phone is unresolved.",
            ]),
            ("[E6] USB Receipt Note | 16 March 2023", [
                'Fictional officer Neel Patil: "Received one unsealed USB from Kavya Rao; '
                'she said a technician copied the clip." Limitation: technician unnamed; '
                "no hash, export log, seal record, device seizure, original storage "
                "preservation or subsequent transfer log is supplied.",
            ]),
            ("[E7] Exercise Property Inventory | 18 March 2023", [
                'Entry: "One USB copy listed. No handset recovered in the materials '
                'recorded here." Limitation: not a certified search record. There is no '
                "supplied recovery, forensic device match, sale trail or admission linking "
                "Arjun to the alleged missing phone.",
            ]),
        ],
    ),
    (
        "Questions for the Courtroom",
        "03 / ARGUMENTS & AGENT BRIEF",
        [
            ("04 | Prosecution Position / To Be Tested", [
                "The prosecution may argue that E1's claimed observation, the reaching "
                "gesture in E2 and the tentative sighting in E3 support its theory of "
                "identity and a taking without permission. It may argue that E4 leaves "
                "a gap in continuous attendance. These are submissions, not findings.",
                "Address why E1 and E5 disagree, whether the E2 figure can be identified, "
                "and how E6's provenance gaps affect reliance on the clip. Do not call "
                "E3 an eyewitness to theft or treat an attendance gap as proof of guilt.",
            ]),
            ("05 | Defense Position / To Be Tested", [
                "The defense may rely on E4 as an alibi lead, E2's obscured face, E3's "
                "uncertainty, E5's conflicting account, and the absence of a recorded "
                "handset recovery in E7. It disputes identity and the alleged taking.",
                "Address E1's direct allegation rather than ignoring it. E4 does not "
                "prove continuous presence; E7 does not itself disprove a taking. No "
                "travel-time calculation or inference of fabricated testimony is justified "
                "on this packet alone.",
            ]),
            ("06 | Disputed Legal Issues / Research, Do Not Assume", [
                "Contextual labels only: IPC section 378 (theft) and section 379 "
                "(punishment for theft). Their mention is not a legal determination that "
                "any ingredient, charge or liability is established. No statute is quoted.",
                "The alleged incident is 15 March 2023, before the BNS commencement. "
                "Check temporal applicability, commencement and savings provisions using "
                "authoritative sources; do not mechanically substitute BNS labels. Also "
                "verify the applicable procedural and electronic-evidence framework.",
                "Identify what must be proved about the property, possession, consent, "
                "intent and alleged movement; assess identity, alibi and competing "
                "timelines. Separate admissibility/authentication questions about E2/E6 "
                "from evidential weight. This packet supplies no precedents.",
            ]),
            ("07 | Missing Information / Priority Requests", [
                "Seek original CCTV and surrounding footage, clock calibration, export "
                "details, hashes and custody records [E2, E6]; inventory/ownership records "
                "and phone identifiers [E1, E7]; original attendance, author and roll-call "
                "method, location and travel evidence [E4]; clarified witness timelines, "
                "sightlines, prior familiarity and customer identity [E1, E3, E5].",
            ]),
            ("08 | Request to Agents / Deliverables", [
                "Prosecution and defense: give your strongest source-cited arguments and "
                "one concession each. Rebut the opposing reading without inventing "
                "evidence. Cite [E1]-[E7] and distinguish quotation, allegation, inference "
                "and verified legal proposition. Mark unknowns explicitly.",
                "Judicial analyst: map agreement and disputes, explain how missing "
                "information could alter analysis, and list targeted follow-up questions. "
                "Verify law before citing it; if research is unavailable, say so. Produce "
                "a provisional issue assessment only, not a verdict or sentence.",
            ]),
        ],
    ),
]


def generate_pdf() -> Path:
    """Write the three-page A4 sample and return its absolute path."""
    objects = [b"", b""]

    def add_object(value: bytes) -> int:
        objects.append(value)
        return len(objects)

    def pdf_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    regular = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    display = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>")
    page_ids = []
    for number, (title, kicker, sections) in enumerate(PAGES, 1):
        commands = []

        def text(x: float, y: float, value: str, font="F1", size=10.5,
                 color="0.16 0.20 0.24") -> None:
            commands.append(
                f"BT /{font} {size} Tf {color} rg 1 0 0 1 {x} {y} Tm "
                f"({pdf_string(value)}) Tj ET"
            )

        commands.append("0.05 0.30 0.33 rg 0 825.89 595.28 16 re f")
        text(48, 793, "NYAYA AI  /  COURTROOM SAMPLE", "F2", 9, "0.05 0.30 0.33")
        text(48, 770, kicker, "F2", 9)
        text(48, 737, title, "F3", 27)
        text(48, 715, "State of Maharashtra v Arjun Mehta  |  Fictional case record", size=10)
        commands.append("0.75 0.81 0.81 RG 0.6 w 48 701 m 547 701 l S")
        y = 680
        for heading, paragraphs in sections:
            text(48, y, heading, "F2", 11, "0.05 0.30 0.33")
            y -= 18
            for paragraph in paragraphs:
                for line in textwrap.wrap(paragraph, width=96):
                    text(48, y, line)
                    y -= 13.2
                y -= 6
            y -= 7
        if y < 72:
            raise ValueError(f"Page {number} overflows safe body area: y={y}")
        commands.append("0.75 0.81 0.81 RG 0.6 w 48 57 m 547 57 l S")
        text(48, 43, "FICTIONAL NAMES & EVENTS / NOT A REAL JUDGMENT / NOT LEGAL ADVICE",
             "F2", 8, "0.05 0.30 0.33")
        text(48, 29, "Demonstration only. No outcome determined. No real personal information.", size=8)
        text(502, 29, f"{number} / 3", "F2", 8)
        stream = "\n".join(commands).encode("ascii")
        content_id = add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream + b"\nendstream"
        )
        page_ids.append(add_object(
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.28 841.89] "
             f"/Resources << /Font << /F1 {regular} 0 R /F2 {bold} 0 R "
             f"/F3 {display} 0 R >> >> /Contents {content_id} 0 R >>").encode("ascii")
        ))
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R /Lang (en-IN) >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count 3 >>".encode("ascii")
    info_id = add_object(
        b"<< /Title (Fictional Indian Theft Case - Courtroom Sample) "
        b"/Author (NyayaAI Demo) /Subject (Fictional case record; not legal advice) >>"
    )
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, value in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{object_id} 0 obj\n".encode("ascii") + value + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
         f"startxref\n{xref}\n%%EOF\n").encode("ascii")
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(result)
    return OUTPUT


if __name__ == "__main__":
    generate_pdf()
