"""
pdf_printer.py — Sahakar Seva Terminal
Generates an A4 PDF of the session summary and silently prints it to the
default Windows printer using pywin32.  No print dialog is shown.

Dependencies:
    pip install reportlab pywin32
"""

import os
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── Colour palette (matches UI) ──────────────────────────────────────────────
DARK_GREEN   = colors.HexColor("#1a4731")
MID_GREEN    = colors.HexColor("#2d6a4f")
LIGHT_GREEN  = colors.HexColor("#d8f3dc")
AMBER        = colors.HexColor("#f5a623")
CREAM        = colors.HexColor("#faf7f0")
DARK_TEXT    = colors.HexColor("#1c1c1e")
GREY_TEXT    = colors.HexColor("#6b7280")
WHITE        = colors.white


def _build_styles():
    base = getSampleStyleSheet()

    header_title = ParagraphStyle(
        "HeaderTitle",
        parent=base["Normal"],
        fontSize=22,
        textColor=WHITE,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    header_sub = ParagraphStyle(
        "HeaderSub",
        parent=base["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#b7e4c7"),
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=base["Normal"],
        fontSize=12,
        textColor=DARK_GREEN,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK_TEXT,
        fontName="Helvetica",
        leading=15,
        spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK_TEXT,
        fontName="Helvetica",
        leading=15,
        leftIndent=12,
        spaceAfter=3,
    )
    label = ParagraphStyle(
        "Label",
        parent=base["Normal"],
        fontSize=9,
        textColor=GREY_TEXT,
        fontName="Helvetica",
    )
    value = ParagraphStyle(
        "Value",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK_TEXT,
        fontName="Helvetica-Bold",
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=base["Normal"],
        fontSize=8,
        textColor=GREY_TEXT,
        fontName="Helvetica",
        alignment=TA_CENTER,
    )
    return {
        "header_title": header_title,
        "header_sub": header_sub,
        "section_title": section_title,
        "body": body,
        "bullet": bullet,
        "label": label,
        "value": value,
        "footer": footer_style,
    }


def generate_summary_pdf(summary: dict, user: dict, jurisdiction: dict | None) -> str:
    """
    Build an A4 PDF for the session summary.

    Parameters
    ----------
    summary     : parsed JSON dict from get_session_summary()
    user        : dict with keys name, occupation, village, land_acres
    jurisdiction: dict with office_name, office_address, nodal_officer, phone  (may be None)

    Returns
    -------
    str — absolute path to the generated PDF temp file
    """
    tmp_fd, pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="sahakar_summary_")
    os.close(tmp_fd)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        title="Sahakar Seva — Session Summary",
        author="Sahakar Seva Terminal",
    )

    styles = _build_styles()
    story = []

    # ── HEADER BAND ──────────────────────────────────────────────────────────
    now_str = datetime.now().strftime("%d %B %Y, %I:%M %p")

    header_data = [[
        Paragraph("🌾 SAHAKAR SEVA TERMINAL", styles["header_title"]),
    ]]
    sub_data = [[
        Paragraph(f"Session Summary  •  {now_str}", styles["header_sub"]),
    ]]

    header_table = Table(header_data, colWidths=[170 * mm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))

    sub_table = Table(sub_data, colWidths=[170 * mm])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MID_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))

    story.extend([header_table, sub_table, Spacer(1, 8 * mm)])

    # ── USER INFO BLOCK ──────────────────────────────────────────────────────
    occ_emoji = {"Farmer": "🌾", "Artisan": "🔨", "Landless Labourer": "👷"}.get(
        user.get("occupation", ""), "👤"
    )
    land_str = (
        f"{user.get('land_acres')} acres" if user.get("land_acres") else "—"
    )
    office_str = "—"
    contact_str = "—"
    if jurisdiction:
        office_str = (
            f"{jurisdiction.get('office_name', '')} — "
            f"{jurisdiction.get('office_address', '')}"
        )
        contact_str = (
            f"{jurisdiction.get('nodal_officer', '')}  |  "
            f"☎ {jurisdiction.get('phone', '')}"
        )

    user_rows = [
        [
            Paragraph("Name / ಹೆಸರು", styles["label"]),
            Paragraph(user.get("name", "—"), styles["value"]),
            Paragraph("Occupation / ವೃತ್ತಿ", styles["label"]),
            Paragraph(f"{occ_emoji} {user.get('occupation', '—')}", styles["value"]),
        ],
        [
            Paragraph("Village / ಗ್ರಾಮ", styles["label"]),
            Paragraph(user.get("village", "—"), styles["value"]),
            Paragraph("Land / ಜಮೀನು", styles["label"]),
            Paragraph(land_str, styles["value"]),
        ],
        [
            Paragraph("Office / ಕಚೇರಿ", styles["label"]),
            Paragraph(office_str, styles["value"]),
            Paragraph("Contact / ಸಂಪರ್ಕ", styles["label"]),
            Paragraph(contact_str, styles["value"]),
        ],
    ]
    col_w = [28 * mm, 57 * mm, 28 * mm, 57 * mm]
    user_table = Table(user_rows, colWidths=col_w)
    user_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), LIGHT_GREEN),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GREEN, CREAM]),
        ("BOX",    (0, 0), (-1, -1), 0.5, MID_GREEN),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b7e4c7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([user_table, Spacer(1, 6 * mm)])

    # ── MAIN ISSUE ───────────────────────────────────────────────────────────
    main_issue = summary.get("main_issue", "—")
    story.append(Paragraph("▶ Main Issue / ಮುಖ್ಯ ಸಮಸ್ಯೆ", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=AMBER, spaceAfter=4))
    story.append(Paragraph(main_issue, styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # ── QUESTIONS DISCUSSED ───────────────────────────────────────────────────
    questions = summary.get("questions_discussed", [])
    story.append(Paragraph("❓ Questions Discussed / ಚರ್ಚಿಸಿದ ಪ್ರಶ್ನೆಗಳು", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=AMBER, spaceAfter=4))
    if questions:
        for i, q in enumerate(questions, 1):
            story.append(Paragraph(f"{i}.  {q}", styles["bullet"]))
    else:
        story.append(Paragraph("—", styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # ── RECOMMENDED NEXT STEPS ───────────────────────────────────────────────
    next_steps = summary.get("recommended_next_steps", "—")
    story.append(Paragraph("✅ Recommended Next Steps / ಮುಂದಿನ ಹಂತಗಳು", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=AMBER, spaceAfter=4))
    story.append(Paragraph(next_steps, styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # ── REQUIRED DOCUMENTS ───────────────────────────────────────────────────
    req_docs = summary.get("required_documents", [])
    story.append(Paragraph("📄 Required Documents / ಅಗತ್ಯ ದಾಖಲೆಗಳು", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=1, color=AMBER, spaceAfter=4))
    if req_docs:
        doc_rows = [[
            Paragraph("☐", styles["body"]),
            Paragraph(d, styles["body"]),
        ] for d in req_docs]
        doc_table = Table(doc_rows, colWidths=[8 * mm, 162 * mm])
        doc_table.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CREAM, WHITE]),
        ]))
        story.append(doc_table)
    else:
        story.append(Paragraph("No specific documents mentioned.", styles["body"]))
    story.append(Spacer(1, 6 * mm))

    # ── REFERENCE SCHEME ─────────────────────────────────────────────────────
    reference = summary.get("reference", "")
    if reference:
        ref_data = [[Paragraph(f"Reference / ಉಲ್ಲೇಖ:  {reference}", styles["body"])]]
        ref_table = Table(ref_data, colWidths=[170 * mm])
        ref_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fff3cd")),
            ("BOX",           (0, 0), (-1, -1), 0.8, AMBER),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ]))
        story.append(ref_table)
        story.append(Spacer(1, 4 * mm))

    # ── FOOTER ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_TEXT, spaceAfter=4))
    story.append(Paragraph(
        "Sahakar Seva Terminal  •  PACS Digital Kiosk  •  This is a computer-generated summary.",
        styles["footer"]
    ))

    doc.build(story)
    return pdf_path


def silent_print(pdf_path: str) -> tuple[bool, str]:
    """
    Send *pdf_path* to the default Windows printer with no dialog.

    Uses win32api.ShellExecute with the "print" verb, which sends the PDF
    directly to the default printer via the system's registered PDF handler
    (Adobe Reader, Edge, etc.).  No dialog window is shown when the handler
    supports silent printing.

    Returns (success: bool, message: str).
    """
    try:
        import win32api
        import win32con

        # ShellExecute verb "print" triggers silent print via default handler
        ret = win32api.ShellExecute(
            0,               # hwnd
            "print",         # verb
            pdf_path,        # file
            None,            # params
            ".",             # working dir
            win32con.SW_HIDE # show — hide any window that might open
        )
        # ShellExecute returns > 32 on success
        if ret > 32:
            return True, "Print job sent successfully."
        else:
            return False, f"ShellExecute returned error code {ret}."

    except ImportError:
        return False, (
            "pywin32 is not installed. "
            "Run: pip install pywin32"
        )
    except Exception as exc:
        return False, f"Print error: {exc}"


def generate_and_print(summary: dict, user: dict, jurisdiction: dict | None) -> dict:
    """
    Convenience wrapper: generate PDF then silent-print.
    Returns a status dict suitable for jsonify().
    """
    try:
        pdf_path = generate_summary_pdf(summary, user, jurisdiction)
    except Exception as exc:
        return {"status": "error", "message": f"PDF generation failed: {exc}"}

    success, message = silent_print(pdf_path)
    if success:
        return {"status": "printed", "message": message, "pdf_path": pdf_path}
    else:
        # Even if printing failed, return the path so the frontend can offer download
        return {"status": "print_error", "message": message, "pdf_path": pdf_path}
