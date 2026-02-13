from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string

from io import BytesIO
import json, os, base64
from datetime import datetime, date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from weasyprint import HTML, CSS

import google.generativeai as genai

from .constants import DESIGNATION_MAP

import uuid
from PyPDF2 import PdfReader, PdfWriter

# ===============================
# DOCUMENT SELECTOR - REMOVED
# ===============================

# ---------------- GEMINI ----------------
genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

# ---------------- LOAD JSON ----------------
BASE_DIR = settings.BASE_DIR
with open(os.path.join(BASE_DIR, "office_order.json"), encoding="utf-8") as f:
    OFFICE_ORDER = json.load(f)

with open(os.path.join(BASE_DIR, "circular.json"), encoding="utf-8") as f:
    CIRCULAR = json.load(f)

with open(os.path.join(BASE_DIR, "policy.json"), encoding="utf-8") as f:
    POLICY = json.load(f)

# ---------------- HELPERS ----------------
def format_date_ddmmyyyy(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        return date_str

# ---------------- HOME ----------------
def home(request):
    return render(request, "generator/home.html", {
        "designations": DESIGNATION_MAP.keys(),
        "people": CIRCULAR["people"]  # Using circular people for both circular and policy
    })

# =====================================================================
# ===================== OFFICE ORDER (UNCHANGED) ======================
# =====================================================================
# Import date class from datetime module
from datetime import date

def generate_body(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    prompt = request.POST.get("body_prompt", "").strip()
    lang = request.POST.get("language", "en")

    # Get current date
    today = date.today().strftime("%d-%m-%Y")

    if lang == "hi":
        system_prompt = f"""
आप BISAG-N के लिए एक आधिकारिक कार्यालय आदेश की मुख्य सामग्री लिख रहे हैं।

नियम:
- कम से कम 2–3 वाक्यों का एक औपचारिक अनुच्छेद लिखें।
- सरकारी भाषा का प्रयोग करें।
- कोई शीर्षक, संदर्भ, दिनांक, प्रेषक या प्राप्तकर्ता न लिखें।
- बुलेट या क्रमांक का प्रयोग न करें।
- केवल सादा पाठ में उत्तर दें।

Today's Date: {today}
"""
    else:
        system_prompt = f"""
You are drafting the BODY of an official government Office Order for BISAG-N.

Rules:
- Write one formal paragraph (minimum 2–3 sentences).
- Use official government tone.
- Do not include title, reference, date, From or To.
- No bullet points or numbering.
- Plain text only.

Today's Date: {today}
"""

    full_prompt = system_prompt + "\n\nTopic:\n" + prompt

    res = gemini_model.generate_content(full_prompt)

    return HttpResponse(res.text.strip())


def result_office_order(request):
    if request.method != "POST":
        return redirect("home")

    lang = request.POST.get("language", "en")
    raw_date = request.POST.get("date")
    date = format_date_ddmmyyyy(raw_date) if raw_date else timezone.now().strftime("%d-%m-%Y")

    # Get reference from form, or use default
    reference = request.POST.get("reference", "").strip()
    if not reference:
        reference = (
            "बायसेग-एन/कार्यालय आदेश/2026/"
            if lang == "hi"
            else "BISAG-N/Office Order/2026/"
        )

    data = {
        "language": lang,
        "header": OFFICE_ORDER["header"][lang],
        "title": OFFICE_ORDER["title_hi"] if lang == "hi" else OFFICE_ORDER["title_en"],
        "reference": reference,
        "date": date,
        "body": request.POST.get("body", "").strip(),
        "from": DESIGNATION_MAP[request.POST.get("from_position")][lang],
        "to": [DESIGNATION_MAP[x][lang] for x in request.POST.getlist("to_recipients[]")],
    }

    request.session["doc_data"] = data
    return render(request, "generator/result_office_order.html", data)

# PDF + DOCX for office order → UNCHANGED
# (your existing download_pdf & download_docx remain exactly same)

# =====================================================================
# ========================= CIRCULAR (UPDATED) ========================
# =====================================================================

def circular_form(request):
    return render(request, "generator/circular_form.html", {
        "people": CIRCULAR["people"]
    })

# -------- GEMINI CIRCULAR BODY --------
def generate_circular_body(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    prompt = request.POST.get("body_prompt", "").strip()
    lang = request.POST.get("language", "en")

    if lang == "hi":
        system_prompt = """
आप BISAG-N के लिए एक सरकारी परिपत्र (Circular) का केवल मुख्य भाग (BODY) लिख रहे हैं।

महत्वपूर्ण नियम:
- केवल परिपत्र का मुख्य विषय-वस्तु लिखें।
- कोई विषय (Subject) न लिखें।
- कोई शीर्षक न लिखें।
- कोई संदर्भ संख्या न लिखें।
- कोई हस्ताक्षर न लिखें।
- कोई दिनांक न लिखें।
- कोई "प्रेषक" या "प्राप्तकर्ता" न लिखें।
- 1–2 औपचारिक अनुच्छेद लिखें।
- सरकारी भाषा का प्रयोग करें।
- केवल सादा पाठ में उत्तर दें।
"""
    else:
        system_prompt = """
You are drafting ONLY the BODY content of an official Government Circular for BISAG-N.

IMPORTANT Rules:
- Write ONLY the main body content of the circular.
- Do NOT include any subject line.
- Do NOT include any title or heading.
- Do NOT include reference number.
- Do NOT include signature.
- Do NOT include date.
- Do NOT include From or To sections.
- Write 1–2 formal paragraphs only.
- Official government tone.
- Plain text only.
"""

    res = gemini_model.generate_content(system_prompt + "\n\nTopic:\n" + prompt)
    return HttpResponse(res.text.strip())

# -------- CIRCULAR PREVIEW --------
def result_circular(request):
    if request.method != "POST":
        return redirect("circular_form")

    lang = request.POST.get("language")
    raw_date = request.POST.get("date")
    date = format_date_ddmmyyyy(raw_date) if raw_date else timezone.now().strftime("%d-%m-%Y")
    subject = request.POST.get("subject")
    body = request.POST.get("body")
    
    # Get from position from dropdown (like office order)
    from_position = request.POST.get("from_position")
    from_designation = DESIGNATION_MAP[from_position][lang] if from_position else ""
    
    to_ids = request.POST.getlist("to[]")

    people = CIRCULAR["people"]
    to_people = [p for p in people if str(p["id"]) in to_ids]

    # Get header based on language
    if lang == "hi":
        header = {
            "org_name": CIRCULAR["header"]["hindi"]["org_name"],
            "ministry": CIRCULAR["header"]["hindi"]["ministry"],
            "government": CIRCULAR["header"]["hindi"]["government"]
        }
    else:
        header = {
            "org_name": CIRCULAR["header"]["english"]["org_name"],
            "ministry": CIRCULAR["header"]["english"]["ministry"],
            "government": CIRCULAR["header"]["english"]["government"]
        }

    data = {
        "language": lang,
        "header": header,
        "date": date,
        "subject": subject,
        "body": body,
        "from": from_designation,
        "to_people": to_people,
    }

    request.session["circular_data"] = data
    return render(request, "generator/result_circular.html", data)

# -------- CIRCULAR PDF --------
def download_circular_pdf(request):
    data = request.session.get("circular_data")
    if not data:
        return HttpResponse("No circular generated", status=400)

    # Add logo path for PDF rendering
    logo_path = os.path.join(settings.BASE_DIR, "static", "generator", "bisag_logo.png")
    if os.path.exists(logo_path):
        data["logo_path"] = f"file:///{logo_path.replace(chr(92), '/')}"
    
    html = render_to_string("generator/pdf_circular.html", data)

    # Optimize PDF generation with font subsetting and compression
    pdf = HTML(
        string=html,
        base_url=str(settings.BASE_DIR)
    ).write_pdf(
        optimize_images=True,
        jpeg_quality=85,
        presentational_hints=True
    )

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Circular.pdf"'
    return response

# -------- CIRCULAR DOCX --------
def download_circular_docx(request):
    from docx.shared import Pt, Inches
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    
    data = request.session.get("circular_data")
    if not data:
        return HttpResponse("No circular generated", status=400)

    doc = Document()
    
    # Set document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Add BISAG Logo
    logo_path = os.path.join(settings.BASE_DIR, "static", "generator", "bisag_logo.png")
    if os.path.exists(logo_path):
        logo_paragraph = doc.add_paragraph()
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo_run = logo_paragraph.add_run()
        logo_run.add_picture(logo_path, height=Inches(0.9))
        doc.add_paragraph()  # Add space after logo

    # Header lines
    for line in data["header"].values():
        p = doc.add_paragraph(line)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].bold = True
        p.runs[0].font.size = Pt(14)

    # Circular title
    lang = data.get("language", "en")
    title_text = "परिपत्र" if lang == "hi" else "Circular"
    p = doc.add_paragraph(title_text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].bold = True
    p.runs[0].underline = True
    p.runs[0].font.size = Pt(16)
    
    # Date
    date_label = "दिनांक :" if lang == "hi" else "Date :"
    p = doc.add_paragraph(f"{date_label} {data['date']}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)

    # Subject
    subject_label = "विषय :" if lang == "hi" else "Subject :"
    p = doc.add_paragraph(f"{subject_label} {data['subject']}")
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)

    # Body
    p = doc.add_paragraph(data["body"])
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.runs[0].font.size = Pt(12)

    # From section
    p = doc.add_paragraph(data["from"])
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)
    
    # Add some space before table
    doc.add_paragraph()
    
    # To section - Table
    to_people = data.get("to_people", [])
    if to_people:
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        
        # Header row
        hdr_cells = table.rows[0].cells
        sr_label = "क्र." if lang == "hi" else "Sr. No."
        name_label = "नाम" if lang == "hi" else "Name"
        sign_label = "हस्ताक्षर" if lang == "hi" else "Sign"
        
        hdr_cells[0].text = sr_label
        hdr_cells[1].text = name_label
        hdr_cells[2].text = sign_label
        
        # Make header bold
        for cell in hdr_cells:
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Data rows
        for idx, person in enumerate(to_people, 1):
            row_cells = table.add_row().cells
            row_cells[0].text = str(idx)
            row_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            name = person.get("name_hi") if lang == "hi" else person.get("name_en")
            row_cells[1].text = name or ""
            row_cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            row_cells[2].text = ""  # Empty for signature
            row_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Set column widths
        table.columns[0].width = Inches(1.0)
        table.columns[1].width = Inches(3.5)
        table.columns[2].width = Inches(1.5)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="Circular.docx"'
    return response

# ===============================
# OFFICE ORDER FORM (MISSING FIX)
# ===============================
def office_order_form(request):
    return render(request, "generator/office_order_form.html", {
        "designations": DESIGNATION_MAP.keys()
    })

# =====================================================================
# ================= OFFICE ORDER PDF & DOCX (RESTORED) =================
# =====================================================================

def download_pdf(request):
    data = request.session.get("doc_data")
    if not data:
        return HttpResponse("No office order generated", status=400)

    html = render_to_string("generator/pdf_office_order.html", data)

    pdf = HTML(
        string=html,
        base_url=settings.BASE_DIR
    ).write_pdf(
        stylesheets=[
            CSS(string="""
                @page { size: A4; margin: 2.5cm; }
                body { font-family: serif; font-size: 12pt; line-height: 1.6; }
                .center { text-align: center; }
                .bold { font-weight: bold; }
                .ref-date-row { display: table; width: 100%; margin: 20px 0; }
                .ref-left { display: table-cell; text-align: left; font-weight: bold; width: 50%; }
                .date-right { display: table-cell; text-align: right; font-weight: bold; width: 50%; }
                .title { text-align: center; font-weight: bold; text-decoration: underline; margin: 20px 0; }
                .body { text-align: justify; margin: 20px 0; }
                .from-section { text-align: right; font-weight: bold; margin: 40px 0 20px; }
                .to-section { margin-top: 20px; }
                .to-section div { margin: 5px 0; }
            """)
        ]
    )

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Office_Order.pdf"'
    return response


def download_docx(request):
    data = request.session.get("doc_data")
    if not data:
        return HttpResponse("No office order generated", status=400)

    doc = Document()

    # Header
    for line in data["header"]:
        p = doc.add_paragraph(line)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].bold = True

    # Reference & Date
    p = doc.add_paragraph(f"Ref: {data['reference']}")
    p.runs[0].bold = True

    p = doc.add_paragraph(f"Date: {data['date']}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True

    # Title
    p = doc.add_paragraph(data["title"])
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].bold = True
    p.runs[0].underline = True

    # Body
    doc.add_paragraph(data["body"])

    # From
    p = doc.add_paragraph(data["from"])
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True

    # To
    for t in data["to"]:
        p = doc.add_paragraph(t)
        p.runs[0].bold = True

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    return HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": 'attachment; filename="Office_Order.docx"'
        }
    )
# =====================================================================
# ========================== POLICY (NEW) =============================
# =====================================================================

# -------- GEMINI POLICY BODY --------
def generate_policy_body(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    prompt = request.POST.get("body_prompt", "").strip()
    lang = request.POST.get("language", "en")

    if lang == "hi":
        system_prompt = """
आप BISAG-N के लिए एक सरकारी नीति (Policy) का केवल मुख्य भाग (BODY) लिख रहे हैं।

महत्वपूर्ण नियम:
- केवल नीति का मुख्य विषय-वस्तु लिखें।
- कोई विषय (Subject) न लिखें।
- कोई शीर्षक न लिखें।
- कोई संदर्भ संख्या न लिखें।
- कोई हस्ताक्षर न लिखें।
- कोई दिनांक न लिखें।
- कोई "प्रेषक" या "प्राप्तकर्ता" न लिखें।
- 1–2 औपचारिक अनुच्छेद लिखें।
- सरकारी भाषा का प्रयोग करें।
- केवल सादा पाठ में उत्तर दें।
"""
    else:
        system_prompt = """
You are drafting ONLY the BODY content of an official Government Policy for BISAG-N.

IMPORTANT Rules:
- Write ONLY the main body content of the policy.
- Do NOT include any subject line.
- Do NOT include any title or heading.
- Do NOT include reference number.
- Do NOT include signature.
- Do NOT include date.
- Do NOT include From or To sections.
- Write 1–2 formal paragraphs only.
- Official government tone.
- Plain text only.
"""

    res = gemini_model.generate_content(system_prompt + "\n\nTopic:\n" + prompt)
    return HttpResponse(res.text.strip())

# -------- POLICY PREVIEW --------
def result_policy(request):
    if request.method != "POST":
        return redirect("home")

    lang = request.POST.get("language")
    raw_date = request.POST.get("date")
    date = format_date_ddmmyyyy(raw_date) if raw_date else timezone.now().strftime("%d-%m-%Y")
    subject = request.POST.get("subject")
    body = request.POST.get("body")
    attached_pdf_name = request.POST.get("attached_pdf_name", "")
    
    # Get from position from dropdown
    from_position = request.POST.get("from_position")
    from_designation = DESIGNATION_MAP[from_position][lang] if from_position else ""
    
    # Get To recipients as designations (not people)
    to_recipients = request.POST.getlist("to_recipients[]")
    to_designations = [DESIGNATION_MAP[x][lang] for x in to_recipients]

    # Get header based on language from policy.json
    if lang == "hi":
        header = {
            "org_name": POLICY["header"]["hi"][0],
            "ministry": POLICY["header"]["hi"][1],
            "government": POLICY["header"]["hi"][2]
        }
    else:
        header = {
            "org_name": POLICY["header"]["en"][0],
            "ministry": POLICY["header"]["en"][1],
            "government": POLICY["header"]["en"][2]
        }

    # Handle PDF upload
    uploaded_pdf = request.FILES.get("policy_pdf")
    pdf_path = None
    pdf_base64 = None
    if uploaded_pdf:
        # Save the uploaded PDF temporarily
        upload_dir = os.path.join(settings.MEDIA_ROOT, "policy_uploads")
        os.makedirs(upload_dir, exist_ok=True)
        pdf_filename = f"policy_{uuid.uuid4().hex}.pdf"
        pdf_path = os.path.join(upload_dir, pdf_filename)
        with open(pdf_path, "wb+") as destination:
            for chunk in uploaded_pdf.chunks():
                destination.write(chunk)
        
        # Convert PDF to base64 for preview
        with open(pdf_path, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode('utf-8')

    data = {
        "language": lang,
        "header": header,
        "date": date,
        "subject": subject,
        "body": body,
        "from": from_designation,
        "to_designations": to_designations,
        "attached_pdf_name": attached_pdf_name,
        "uploaded_pdf_path": pdf_path,
    }

    # Store in session (without large base64)
    request.session["policy_data"] = data
    
    # Add pdf_base64 only for template rendering (not in session)
    if pdf_base64:
        data["pdf_base64"] = pdf_base64
    
    return render(request, "generator/result_policy.html", data)

# -------- POLICY PDF --------
def download_policy_pdf(request):
    data = request.session.get("policy_data")
    if not data:
        return HttpResponse("No policy generated", status=400)

    # Add logo path for PDF rendering
    logo_path = os.path.join(settings.BASE_DIR, "static", "generator", "bisag_logo.png")
    if os.path.exists(logo_path):
        data["logo_path"] = f"file:///{logo_path.replace(chr(92), '/')}"
    
    html = render_to_string("generator/pdf_policy.html", data)

    # Generate first page PDF
    first_page_pdf = HTML(
        string=html,
        base_url=str(settings.BASE_DIR)
    ).write_pdf(
        optimize_images=True,
        jpeg_quality=85,
        presentational_hints=True
    )

    # Check if there's an uploaded PDF to merge
    uploaded_pdf_path = data.get("uploaded_pdf_path")
    
    if uploaded_pdf_path and os.path.exists(uploaded_pdf_path):
        try:
            # Use PdfWriter to merge PDFs
            pdf_writer = PdfWriter()
            
            # Add first page (generated policy)
            first_page_reader = PdfReader(BytesIO(first_page_pdf))
            for page in first_page_reader.pages:
                pdf_writer.add_page(page)
            
            # Add uploaded PDF pages
            uploaded_reader = PdfReader(uploaded_pdf_path)
            for page in uploaded_reader.pages:
                pdf_writer.add_page(page)
            
            # Write merged PDF
            output = BytesIO()
            pdf_writer.write(output)
            output.seek(0)
            final_pdf = output.read()
            
            # Clean up uploaded file
            try:
                os.remove(uploaded_pdf_path)
            except:
                pass
        except Exception as e:
            print(f"Error merging PDFs: {e}")
            final_pdf = first_page_pdf
    else:
        final_pdf = first_page_pdf

    response = HttpResponse(final_pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="Policy.pdf"'
    return response

# -------- POLICY DOCX --------
def download_policy_docx(request):
    from docx.shared import Pt, Inches
    
    data = request.session.get("policy_data")
    if not data:
        return HttpResponse("No policy generated", status=400)

    doc = Document()
    
    # Set document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Add BISAG Logo
    logo_path = os.path.join(settings.BASE_DIR, "static", "generator", "bisag_logo.png")
    if os.path.exists(logo_path):
        logo_paragraph = doc.add_paragraph()
        logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        logo_run = logo_paragraph.add_run()
        logo_run.add_picture(logo_path, height=Inches(0.9))
        doc.add_paragraph()  # Add space after logo

    # Header lines
    for line in data["header"].values():
        p = doc.add_paragraph(line)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].bold = True
        p.runs[0].font.size = Pt(14)

    # Policy title
    lang = data.get("language", "en")
    title_text = "नीति" if lang == "hi" else "Policy"
    p = doc.add_paragraph(title_text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].bold = True
    p.runs[0].underline = True
    p.runs[0].font.size = Pt(16)
    
    # Date
    date_label = "दिनांक :" if lang == "hi" else "Date :"
    p = doc.add_paragraph(f"{date_label} {data['date']}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)

    # Subject
    subject_label = "विषय :" if lang == "hi" else "Subject :"
    p = doc.add_paragraph(f"{subject_label} {data['subject']}")
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)

    # Body
    p = doc.add_paragraph(data["body"])
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.runs[0].font.size = Pt(12)

    # From section
    p = doc.add_paragraph(data["from"])
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)
    
    # Add some space before To section
    doc.add_paragraph()
    
    # To section - Bullet Points
    to_label = "प्रति :" if lang == "hi" else "To :"
    p = doc.add_paragraph(to_label)
    p.runs[0].bold = True
    p.runs[0].font.size = Pt(12)
    
    to_designations = data.get("to_designations", [])
    for designation in to_designations:
        p = doc.add_paragraph(designation, style='List Bullet')
        p.runs[0].font.size = Pt(11)
    
    # Attached section
    attached_label = "संलग्न :" if lang == "hi" else "Attached :"
    p = doc.add_paragraph(f"{attached_label} {data['attached_pdf_name']}")
    p.runs[0].font.size = Pt(12)
    
    # Try to convert and add PDF pages as images
    uploaded_pdf_path = data.get("uploaded_pdf_path")
    if uploaded_pdf_path and os.path.exists(uploaded_pdf_path):
        try:
            from pdf2image import convert_from_path
            
            # Ensure temp directory exists
            temp_dir = os.path.join(settings.MEDIA_ROOT, "policy_uploads")
            os.makedirs(temp_dir, exist_ok=True)
            
            # Add page break before attached content
            doc.add_page_break()
            
            # Convert PDF pages to images with better quality
            try:
                # Try conversion with explicit error handling
                images = convert_from_path(uploaded_pdf_path, dpi=200, fmt='png')
                
                for idx, image in enumerate(images):
                    # Save image temporarily
                    temp_img_path = os.path.join(temp_dir, f"temp_page_{uuid.uuid4().hex}_{idx}.png")
                    
                    try:
                        image.save(temp_img_path, "PNG")
                        
                        # Add page break for subsequent pages
                        if idx > 0:
                            doc.add_page_break()
                        
                        # Add image to document
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        run = p.add_run()
                        run.add_picture(temp_img_path, width=Inches(6.5))
                        
                        # Clean up temp image immediately after adding
                        try:
                            os.remove(temp_img_path)
                        except Exception as rm_error:
                            print(f"Cleanup error: {rm_error}")
                            
                    except Exception as img_error:
                        print(f"Image processing error for page {idx}: {img_error}")
                        continue
                
                # Clean up uploaded PDF after successful processing
                try:
                    os.remove(uploaded_pdf_path)
                except Exception as cleanup_error:
                    print(f"PDF cleanup error: {cleanup_error}")
                    
            except Exception as conv_error:
                # Likely poppler not installed
                print(f"PDF conversion error: {conv_error}")
                doc.add_page_break()
                p = doc.add_paragraph("Note: Attached PDF pages could not be converted to images.")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].italic = True
                
                p = doc.add_paragraph("This requires 'poppler' to be installed on your system.")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].italic = True
                p.runs[0].font.size = Pt(10)
                
                p = doc.add_paragraph("Please download the complete document as PDF to view all pages.")
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].italic = True
                p.runs[0].font.size = Pt(10)
                
        except ImportError as imp_err:
            # pdf2image not available
            print(f"ImportError: {imp_err}")
            doc.add_page_break()
            p = doc.add_paragraph("[PDF attachment module not available - download as PDF to view complete document]")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].italic = True
        except Exception as e:
            print(f"Error processing PDF attachment: {e}")
            doc.add_page_break()
            p = doc.add_paragraph(f"[Error loading attached PDF - download as PDF for complete document]")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.runs[0].italic = True

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="Policy.docx"'
    return response
