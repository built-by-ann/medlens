"""One-off script to render demo discharge summaries as real PDF files.

Not part of the application - regenerates the two PDF demo documents under
frontend/public/demo/. Run from frontend/ using the backend's virtualenv
(reportlab is already a backend dev dependency, used for the same purpose
in backend/tests/test_clinical_documents.py):

    ../backend/.venv/bin/python scripts/generate-demo-pdfs.py

Nothing in the frontend build imports this file.
"""

import sys
import textwrap

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = letter
LEFT_MARGIN = 72
TOP_MARGIN = 72
LINE_HEIGHT = 14
WRAP_WIDTH = 95


def render_pdf(out_path: str, paragraphs: list[str]) -> None:
    pdf = canvas.Canvas(out_path, pagesize=letter)
    pdf.setFont("Helvetica", 10)
    y = PAGE_HEIGHT - TOP_MARGIN

    for paragraph in paragraphs:
        if paragraph == "":
            y -= LINE_HEIGHT
            if y < 72:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = PAGE_HEIGHT - TOP_MARGIN
            continue

        for line in textwrap.wrap(paragraph, WRAP_WIDTH) or [""]:
            if y < 72:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = PAGE_HEIGHT - TOP_MARGIN
            pdf.drawString(LEFT_MARGIN, y, line)
            y -= LINE_HEIGHT

    pdf.save()


ROBERT_ALVAREZ = [
    "Hospital Discharge Summary",
    "Patient: Robert Alvarez",
    "Admission date: August 1, 2026    Discharge date: August 5, 2026",
    "Service: Cardiology",
    "",
    "Diagnosis: Acute decompensated heart failure, resolved with intravenous "
    "diuresis.",
    "",
    "Hospital course: Mr. Alvarez was admitted with acute decompensated "
    "heart failure and treated with intravenous Furosemide, transitioning "
    "to an oral dose of 40 mg twice daily prior to discharge. Lisinopril "
    "5 mg oral once daily was started for afterload reduction and "
    "tolerated well, with stable renal function and potassium. "
    "Metoprolol tartrate was discontinued and switched to metoprolol "
    "succinate 50 mg oral once daily for improved once-daily dosing. "
    "Amlodipine was discontinued given its likely contribution to the "
    "peripheral edema on presentation. He diuresed well, returning to his "
    "dry weight, and was ambulating without dyspnea at discharge.",
    "",
    "Discharge medications:",
    "- Furosemide 40 mg oral twice daily",
    "- Lisinopril 5 mg oral once daily",
    "- Metoprolol succinate 50 mg oral once daily",
    "- Atorvastatin 20 mg oral nightly",
    "- Aspirin 81 mg oral once daily",
    "",
    "Discontinued during this admission:",
    "- Amlodipine 10 mg oral once daily - discontinued (peripheral edema)",
    "- Metoprolol tartrate 25 mg oral twice daily - discontinued (replaced "
    "by succinate formulation)",
    "",
    "Follow-up: Cardiology clinic in one week. Basic metabolic panel to "
    "recheck renal function and potassium at that visit.",
]

DOROTHY_WILLIAMS = [
    "Hospital Discharge Summary",
    "Patient: Dorothy Williams",
    "Admission date: September 2, 2026    Discharge date: September 4, 2026",
    "Service: Cardiology",
    "",
    "Diagnosis: Atrial fibrillation with rapid ventricular response, "
    "resolved.",
    "",
    "Hospital course: Ms. Williams, an 82-year-old with a history of "
    "atrial fibrillation, chronic kidney disease stage 3, type 2 "
    "diabetes, and osteoarthritis, was admitted with atrial fibrillation "
    "with rapid ventricular response. Rate control was achieved with "
    "adjustment of her home regimen. Warfarin was increased from 5 mg to "
    "7.5 mg oral once daily given a subtherapeutic INR on her prior dose; "
    "INR to be rechecked in one week. Furosemide was held during the "
    "admission due to transient hypotension and restarted at discharge "
    "at a reduced dose of 20 mg oral once daily, down from her home dose "
    "of 40 mg. Per nephrology, ibuprofen was discontinued given its "
    "contribution to her declining renal function; acetaminophen 500 mg "
    "oral as needed was started in its place for osteoarthritis pain.",
    "",
    "Discharge medications:",
    "- Warfarin 7.5 mg oral once daily",
    "- Furosemide 20 mg oral once daily",
    "- Losartan 50 mg oral once daily",
    "- Metformin 1000 mg oral twice daily",
    "- Calcium carbonate / Vitamin D3 600 mg / 400 IU oral twice daily",
    "- Acetaminophen 500 mg oral as needed",
    "",
    "Discontinued during this admission:",
    "- Ibuprofen 400 mg oral three times daily as needed - discontinued "
    "(nephrology, due to chronic kidney disease)",
    "",
    "Follow-up: Primary care in one week; INR recheck per anticoagulation "
    "clinic.",
]


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "both"

    if target in ("robert", "both"):
        render_pdf(
            "public/demo/robert-alvarez/03-discharge-summary.pdf",
            ROBERT_ALVAREZ,
        )
        print("wrote public/demo/robert-alvarez/03-discharge-summary.pdf")

    if target in ("dorothy", "both"):
        render_pdf(
            "public/demo/dorothy-williams/03-discharge-summary.pdf",
            DOROTHY_WILLIAMS,
        )
        print("wrote public/demo/dorothy-williams/03-discharge-summary.pdf")
