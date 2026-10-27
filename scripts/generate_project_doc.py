"""
Generate a comprehensive, publication-grade Word (.docx) document
detailing the entire REX AI project for Andalusia Academy.
"""
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, hex_color: str):
    """Set the background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner margins (padding) for a cell in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def add_callout(doc, text: str, title: str = "ملاحظة هامة / Important Note", border_color="0D9488", bg_color="F0FDFA"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=140)
    
    # Left border only
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    run_t = p.add_run(f"📌 {title}\n")
    run_t.bold = True
    run_t.font.size = Pt(10.5)
    run_t.font.color.rgb = RGBColor(13, 148, 136)
    
    run_b = p.add_run(text)
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = RGBColor(30, 41, 59)
    doc.add_paragraph() # space after table

def style_heading_1(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(18)
    run.bold = True
    run.font.color.rgb = RGBColor(15, 23, 42) # Dark Slate
    return p

def style_heading_2(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(14)
    run.bold = True
    run.font.color.rgb = RGBColor(30, 58, 138) # Deep Blue
    return p

def style_heading_3(doc, text: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(12)
    run.bold = True
    run.font.color.rgb = RGBColor(13, 148, 136) # Teal
    return p

def add_body_p(doc, text: str, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(51, 65, 85) # Slate text
    return p

def add_bullet(doc, title: str, text: str):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run_t = p.add_run(title + (" — " if title else ""))
    run_t.bold = True
    run_t.font.name = "Calibri"
    run_t.font.size = Pt(10)
    run_t.font.color.rgb = RGBColor(15, 23, 42)
    
    run_b = p.add_run(text)
    run_b.font.name = "Calibri"
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = RGBColor(51, 65, 85)
    return p

def style_table(table, header_bg="1E3A8A", alt_bg="F8FAFC"):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Format header
    for cell in table.rows[0].cells:
        set_cell_background(cell, header_bg)
        set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
        for p in cell.paragraphs:
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            for r in p.runs:
                r.bold = True
                r.font.name = "Calibri"
                r.font.size = Pt(10)
                r.font.color.rgb = RGBColor(255, 255, 255)
                
    # Format content rows
    for r_idx, row in enumerate(table.rows[1:], start=1):
        bg = alt_bg if r_idx % 2 == 1 else "FFFFFF"
        for cell in row.cells:
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
            for p in cell.paragraphs:
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.1
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(30, 41, 59)

def build_document():
    doc = docx.Document()
    
    # Page setup: Standard A4, 1-inch margins
    sections = doc.sections
    for s in sections:
        s.page_width = Inches(8.27)  # A4
        s.page_height = Inches(11.69)
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)
        
    # ==========================================================
    # COVER / HEADER BANNER
    # ==========================================================
    header_tbl = doc.add_table(rows=1, cols=1)
    header_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    header_tbl.autofit = False
    header_tbl.columns[0].width = Inches(6.5)
    c0 = header_tbl.cell(0, 0)
    set_cell_background(c0, "0F172A") # Midnight Slate
    set_cell_margins(c0, top=260, bottom=260, left=240, right=240)
    
    p0 = c0.paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p0.add_run("ANDALUSIA ACADEMY • AI INNOVATION SUITE\n")
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(11)
    r_sub.bold = True
    r_sub.font.color.rgb = RGBColor(45, 212, 191) # Light Teal
    
    r_title = p0.add_run("REX AI — Smart Academy Multi-Agent System\n")
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(22)
    r_title.bold = True
    r_title.font.color.rgb = RGBColor(255, 255, 255)
    
    r_ar = p0.add_run("نظام الوكلاء الأذكياء المتعدد لأكاديمية أندلسية — التوثيق الشامل والمعماري للمشروع\n")
    r_ar.font.name = "Calibri"
    r_ar.font.size = Pt(13)
    r_ar.font.color.rgb = RGBColor(203, 213, 225)
    
    r_ver = p0.add_run("\nFull Architecture • Multi-Agent Workflows • API & UI Reference • Test Audit\nSprint 2 & Operational Release • October 2026")
    r_ver.font.name = "Calibri"
    r_ver.font.size = Pt(9.5)
    r_ver.font.color.rgb = RGBColor(148, 163, 184)
    
    doc.add_paragraph() # Spacing
    
    # Metadata Info Table
    meta_tbl = doc.add_table(rows=5, cols=2)
    meta_tbl.columns[0].width = Inches(2.2)
    meta_tbl.columns[1].width = Inches(4.3)
    
    meta_data = [
        ("اسم المشروع / Project Name", "REX AI — Smart Academy Multi-Agent System"),
        ("المؤسسة المستفيدة / Organization", "أكاديمية أندلسية للتدريب والاستشارات (Andalusia Academy)"),
        ("فريق العمل والتطوير / Engineering Team", "Faris Ahmed (فارس أحمد) • AbdulRahman Adham (عبدالرحمن أدهم) • Ahmed AlAbiad (أحمد الأبيض)"),
        ("حالة النظام الحالية / System Status", "جاهز للاستخدام العملي، 370 اختبار آلي ناجح 100%، واجهات FastAPI و Streamlit شغالة"),
        ("تاريخ الإصدار / Version & Date", "Version 2.0 (Sprint 2 Integrated) — October 2026"),
    ]
    
    for idx, (label, val) in enumerate(meta_data):
        row = meta_tbl.rows[idx]
        row.cells[0].paragraphs[0].add_run(label).bold = True
        row.cells[1].paragraphs[0].add_run(val)
        
    style_table(meta_tbl, header_bg="1E293B", alt_bg="F1F5F9")
    doc.add_paragraph()
    
    add_callout(
        doc,
        "تم فحص النظام بالكامل والتأكد من اجتياز جميع الاختبارات البرمجية الآلية بنجاح (370 Passed / 0 Failed). "
        "تم ربط واجهات FastAPI الخلفية بتطبيق Streamlit الأمامي بكافة وكلائه الخمسة مع تفعيل ضوابط الحماية "
        "وعزل بيانات العرض التجريبي (Demo Mode) عن بيانات الأكاديمية الحقيقية (Academy Mode).",
        title="ملخص الفحص التقني الفوري (Technical Verification)"
    )

    # ==========================================================
    # SECTION 1: EXECUTIVE SUMMARY
    # ==========================================================
    style_heading_1(doc, "1. الملخص التنفيذي للمشروع (Executive Summary)")
    
    add_body_p(
        doc,
        "مشروع REX AI هو منصة ذكاء اصطناعي متعددة الوكلاء (Multi-Agent AI System) صُممت خصيصاً لتلبية احتياجات "
        "أكاديمية أندلسية التعليمية والإدارية. الهدف الجوهري للنظام هو تحويل العمليات اليدوية المعقدة والمستهلكة للوقت "
        "— مثل توجيه الطلاب وإرشادهم، البحث عن المناقصات الحكومية والخاصة وتحليل كراسات الشروط، وتصميم المناهج التدريبية "
        "وفق معايير الاعتماد الدولية، وإعداد المستندات الرسمية، وتوليد الحملات التسويقية — إلى منظومة عمل مؤتمتة، فائقة الدقة، "
        "وتعتمد على الذكاء الاصطناعي التوليدي الموثوق مع إشراف ومراجعة بشرية صارمة (Human-in-the-Loop)."
    )
    
    add_bullet(doc, "حل مشكلة الهلوسة وانعدام الدقة (Zero Hallucination Guarantee)", 
               "يعتمد النظام على بنية استرجاع معززة بالتوليد (Grounded RAG) مستندة إلى قاعدة بيانات متجهات ChromaDB، بحيث لا يقدم المساعد أي معلومة أو سعر أو شرط تدريبي ما لم تكن مستخرجة حرفياً وموثقة من مستندات الأكاديمية المعتمدة رسمياً.")
    
    add_bullet(doc, "فصل الصلاحيات والأمان (Enterprise Security Boundaries)", 
               "يوفر النظام بوابتين منفصلتين: واجهة عامة للطلاب والجمهور لا تتطلب صلاحيات لكنها مقيدة ببيانات الكتالوج المنشور، وواجهة إدارية آمنة للموظفين (Staff Portal) محمية بمفتاح وصول سري (API Key) للتحكم في اعتماد البرامج، وتوليد المستندات، وإدارة المناقصات، وتعديل المناهج.")
               
    add_bullet(doc, "عزل البيئات التجريبية (Demo vs Academy Isolation)", 
               "يحتوي النظام على نمط عرض تجريبي مخصص للمناقشة والتقييم (TA Demo Mode) يستخدم بيانات وهمية مفصولة كلياً في مجلد data/demo عن مجلدات الأكاديمية الرسمية data/catalog لضمان عدم تسريب بيانات غير موثقة.")

    # ==========================================================
    # SECTION 2: SYSTEM ARCHITECTURE & TECH STACK
    # ==========================================================
    style_heading_1(doc, "2. المعمارية التقنية وحزمة التكنولوجيا (Technology Stack & Architecture)")
    
    add_body_p(
        doc,
        "تم بناء نظام REX AI وفق معمارية برمجية قياسية حديثة، تفصل بين طبقة الخدمات الخلفية (Backend API)، "
        "وطبقة الواجهات الأمامية (Frontend Presentation)، وطبقة تخزين المتجهات والبيانات العلائقية، "
        "وطبقة نماذج الذكاء الاصطناعي:"
    )
    
    tech_table = doc.add_table(rows=9, cols=3)
    tech_table.columns[0].width = Inches(1.8)
    tech_table.columns[1].width = Inches(2.2)
    tech_table.columns[2].width = Inches(2.5)
    
    tech_rows = [
        ("المكون / Layer", "التقنية المستخدمة / Technology", "الوظيفة والمسؤولية / Role & Rationale"),
        ("الواجهة الأمامية (Frontend)", "Streamlit (Multi-Page UI)", "واجهة تفاعلية فورية تدعم اللغة العربية والإنجليزية، للطلاب والمشرفين"),
        ("واجهة برمجة التطبيقات (Backend)", "FastAPI + Uvicorn (ASGI)", "سيرفر عالي السرعة، معالجة غير متزامنة، التحقق الصارم عبر Pydantic v2"),
        ("نماذج التوليد (LLM Engine)", "Google Gemini API (gemini-3.5-flash)", "التوليد المنطقي والاستدلال مع ضبط منخفض لزمن الاستجابة (low thinking)"),
        ("المتجهات والتضمين (Embeddings)", "Gemini Embedding 2 (768 dims)", "توليد المتجهات بدقة 768 بعد لتمثيل المعنى السياقي للمحتوى التعليمي"),
        ("قاعدة بيانات المتجهات (Vector DB)", "ChromaDB (Persistent)", "تخزين واسترجاع مقاطع المستندات المعتمدة وفقاً لتشابه الجيب التمام (Cosine Similarity)"),
        ("قاعدة البيانات العلائقية (Relational DB)", "SQLite + SQLAlchemy 2.0", "تخزين سجلات المناقصات، المناهج، اعتمادات الكورسات، والطلاب المسجلين"),
        ("معالجة المستندات (Doc Processing)", "PyMuPDF (Fitz) + python-docx", "استخراج النصوص وهياكل الصفحات من ملفات PDF و Word و Markdown وتوليدها"),
        ("بروتوكول الأدوات (Extensibility)", "FastMCP / Model Context Protocol", "بروتوكول معياري لربط أدوات النظام الآلية بنماذج الذكاء الاصطناعي بشكل آمن"),
    ]
    
    for r_idx, row_vals in enumerate(tech_rows):
        for c_idx, val in enumerate(row_vals):
            tech_table.rows[r_idx].cells[c_idx].paragraphs[0].add_run(val)
            
    style_table(tech_table)
    doc.add_paragraph()

    # ==========================================================
    # SECTION 3: THE FIVE SPECIALIZED AI AGENTS
    # ==========================================================
    style_heading_1(doc, "3. منظومة الوكلاء الأذكياء الخمسة (The 5 Specialized AI Agents)")
    
    add_body_p(
        doc,
        "يتكون REX AI من خمسة وكلاء أذكياء متخصصين، يعمل كل وكيل بشكل مستقل على إنجاز مهام معقدة، "
        "مع إمكانية تبادل البيانات والتنسيق عبر واجهات موحدة:"
    )
    
    # Agent 1
    style_heading_2(doc, "3.1 الوكيل الأول: REX Course Assistant & Guided Recommendation")
    add_body_p(
        doc,
        "الوكيل المسؤول عن مساعدة الطلاب والراغبين في التعلم في اختيار البرامج التدريبية الملائمة بدقة. "
        "يعمل الوكيل بنمطين متكاملين:"
    )
    add_bullet(doc, "النمط الأول: الاستفسار المباشر (Direct Knowledge Retrieval)", 
               "الإجابة على أسئلة المتدربين حول محتوى الكورسات، الأسعار، المدد الزمنية، والمتطلبات السابقة، مع الالتزام التام بالاستشهاد بالمصادر الرسمية، ورفض الإجابة عن أي معلومة غير موثقة.")
    add_bullet(doc, "النمط الثاني: المقابلة التأهيلية الموجهة (Guided Learner Qualification)", 
               "إجراء حوار تفاعلي ذكي يطرح فيه الوكيل أسئلة محددة عن الخلفية التقنية، مستوى المهارة الحالي، الهدف الوظيفي، الميزانية، وطريقة التدريب المفضلة (حضوري / عن بعد). يتم حفظ حالة الجلسة (Session State) في SQLite، وتطبيق قواعد تصفية قطعية لاستبعاد الكورسات غير المناسبة وترشيح الكورس الأفضل، مع جمع بيانات التواصل بموافقة المتدرب (Consent-based Lead Capture).")

    # Agent 2
    style_heading_2(doc, "3.2 الوكيل الثاني: RFP & Tender Research Agent")
    add_body_p(
        doc,
        "الوكيل المسؤول عن مراقبة واكتشاف وتحليل الفرص والمناقصات الحكومية والخاصة (RFPs & Tenders) في مجالات التدريب والتعليم "
        "والتطوير المهني والتقني عبر منطقة الشرق الأوسط وشمال أفريقيا (مصر، السعودية، الإمارات، وغيرها)."
    )
    add_bullet(doc, "الزحف واستيراد المناقصات (Ingestion & Scraping)", 
               "فحص مصادر العطاءات، أو استيراد كراسات الشروط وملفات المناقصات بصيغ PDF و Word و Excel.")
    add_bullet(doc, "التحليل والمطابقة الذكية (AI Matching & Relevance Scoring)", 
               "تحليل المتطلبات والشروط، واحتساب درجة التوافق (Relevance Score من 0 إلى 100) مع قدرات وإمكانيات أكاديمية أندلسية، وتحديد مواعيد التقديم النهائية والشروط الجزائية ومستويات المخاطر.")
    add_bullet(doc, "نظام التنبيهات والأرشفة (Alerts & Persistence)", 
               "إرسال تنبيهات بريدية أو إشعارات داخلية للفرص ذات الأولوية العالية، وتخزين سجل المناقصات في قاعدة بيانات rfp.db لإتاحة مراجعتها وتحديث حالتها.")

    # Agent 3
    style_heading_2(doc, "3.3 الوكيل الثالث: Curriculum & Accreditation Alignment Agent")
    add_body_p(
        doc,
        "أحد أقوى وأحدث أجزاء النظام؛ يتيح لأعضاء هيئة التدريس ومطوري المناهج بناء خطط دراسية متكاملة "
        "وفحص مدى توافقها مع أطر الاعتماد الأكاديمي والمهني المحلية والدولية."
    )
    add_bullet(doc, "أبحاث الموضوعات الذكية (AI Subject Research)", 
               "استكشاف أحدث الاتجاهات العالمية، والمهارات المطلوبة في سوق العمل، وتوصيات كبرى الشركات العالمية لموضوع التدريب المختار.")
    add_bullet(doc, "بناء الخطة الدراسية وتصنيف بلوم (Curriculum Generation & Bloom's Taxonomy)", 
               "توليد وحدات دراسية مفصلة (Modules)، وتحديد أهداف التعلم القابلة للقياس (CLOs) وفق مستويات بلوم (تذكر، فهم، تطبيق، تحليل، تقييم، ابتكار)، وتوزيع الساعات التدريبية العملية والنظرية.")
    add_bullet(doc, "المطابقة مع أطر الاعتماد المعتمدة (Accreditation Alignment Matrix)", 
               "يحتوي النظام على محرك مطابقة مبني داخلياً يربط المنهج بـ 5 أطر اعتماد كبرى:"
               "\n- NCAAA (المركز الوطني للتقويم والاعتماد الأكاديمي - السعودية)"
               "\n- ABET (مجلس الاعتماد للهندسة والتكنولوجيا - المعيار الأمريكي والدولي)"
               "\n- TVTC (المؤسسة العامة للتدريب التقني والمهني - السعودية)"
               "\n- QQA (هيئة جودة التعليم والتدريب - البحرين)"
               "\n- Pearson BTEC (الاعتماد المهني البريطاني الدولي)")
    add_bullet(doc, "تصدير تقارير PDF احترافية (Professional PDF Export)", 
               "توليد تقرير رسمي منسق يتضمن مصفوفة التوافق، نسب التغطية، وفجوات الامتثال لدعم طلبات الاعتماد الأكاديمي.")

    # Agent 4
    style_heading_2(doc, "3.4 الوكيل الرابع: Educational Document Generation Agent")
    add_body_p(
        doc,
        "الوكيل المسؤول عن تحويل بيانات البرامج التدريبية المعتمدة إلى وثائق رسمية ومواد تسويقية جاهزة للطباعة والنشر."
    )
    add_bullet(doc, "ثلاثة أنواع رئيسية من المستندات", 
               "1) مقترح تدريبي متكامل للمؤسسات والشركات (Corporate Training Proposal)\n"
               "2) كتيب تسويقي للمتدربين (Student Program Brochure)\n"
               "3) توصيف مقرر أكاديمي تفصيلي (Detailed Course Syllabus)")
    add_bullet(doc, "دعم ثنائي اللغة والتنسيقات (Bilingual DOCX & PDF)", 
               "توليد المستندات باللغتين العربية والإنجليزية بجودة تنسيق احترافية، مع دعم التنزيل بصيغتي Microsoft Word (.docx) و Adobe PDF.")
    add_bullet(doc, "دورة مراجعة واعتماد الموظفين (Staff Review Cycle)", 
               "تخضع المستندات المولدة لحالة مسودة (Draft) ولا تعتمد رسمياً إلا بعد مراجعة الموظف المسؤول وإبداء ملاحظاته أو موافقته.")

    # Agent 5
    style_heading_2(doc, "3.5 الوكيل الخامس: AI Marketing Agent")
    add_body_p(
        doc,
        "الوكيل المسؤول عن صياغة وتوليد الحملات التسويقية المتكاملة للبرامج التدريبية الجديدة والمحدثة."
    )
    add_bullet(doc, "تحديد الجمهور المستهدف وشخصيات المشترين (Audience Personas)", 
               "تحليل متطلبات الكورس وتحديد الفئات المستهدفة من خريجين، مهنيين، وباحثين عن عمل.")
    add_bullet(doc, "توليد محتوى متعدد القنوات (Omnichannel Campaign Assets)", 
               "صياغة منشورات احترافية لشبكة LinkedIn، تغريدات لمنصة X/Twitter، محتوى بصري لـ Instagram، ورسائل بريد إلكتروني تسويقية مع عبارات الحث على اتخاذ إجراء (Call to Action).")

    # ==========================================================
    # SECTION 4: DATA PIPELINE & QUALITY INGESTION
    # ==========================================================
    style_heading_1(doc, "4. دورة معالجة البيانات واعتماد الكورسات (Data Ingestion & Approval Pipeline)")
    
    add_body_p(
        doc,
        "تعتبر دورة حياة المستندات في REX AI من أهم ميزات الأمان التي تمنع نشر أي محتوى تدريبي قبل تدقيقه. "
        "تمر البيانات بالخطوات التالية:"
    )
    
    pipe_table = doc.add_table(rows=6, cols=3)
    pipe_table.columns[0].width = Inches(1.2)
    pipe_table.columns[1].width = Inches(2.3)
    pipe_table.columns[2].width = Inches(3.0)
    
    pipe_rows = [
        ("المرحلة / Step", "الإجراء الفني / Technical Action", "الضوابط والتحقق / Controls & Invariants"),
        ("1. الرفع (Upload)", "رفع الملف بصيغة PDF, DOCX, MD عبر واجهة الموظف", "حساب بصمة التجزئة SHA-256 لمنع التكرار والعبث، وحفظ الأصل في مجلد محمي"),
        ("2. الاستخراج (Extraction)", "قراءة النصوص وتحديد الجداول والهياكل عبر PyMuPDF", "كشف الصفحات الممسوحة ضوئياً وتحديد الصفحات الفارغة والتنبيه بجودتها"),
        ("3. التقطيع (Chunking)", "تقطيع النص إلى أجزاء بحجم ~400 Token وتداخل 60 Token", "الحفاظ على حدود المقاطع والوحدات التدريبية والعناوين وأرقام الصفحات"),
        ("4. الفحص والمراجعة (Review)", "عرض المسودة على الموظف في لوحة Course Approvals", "إمكانية قبول الكورس أو رفضه مع تسجيل سبب الرفض واسم المراجع رسمياً"),
        ("5. النشر والتضمين (Publish)", "توليد المتجهات ونشر الكورس في ChromaDB و SQLite", "لا يظهر الكورس في كتالوج الطلاب أو محرك RAG إلا بعد تمام الاعتماد"),
    ]
    
    for r_idx, row_vals in enumerate(pipe_rows):
        for c_idx, val in enumerate(row_vals):
            pipe_table.rows[r_idx].cells[c_idx].paragraphs[0].add_run(val)
            
    style_table(pipe_table, header_bg="0D9488")
    doc.add_paragraph()

    # ==========================================================
    # SECTION 5: API ENDPOINTS DIRECTORY
    # ==========================================================
    style_heading_1(doc, "5. دليل واجهات البرمجة الخلفية (FastAPI Endpoints Reference)")
    
    add_body_p(
        doc,
        "يوفر النظام مجموعة متكاملة من واجهات RESTful APIs الآمنة، مقسمة حسب النطاقات الوظيفية:"
    )
    
    api_table = doc.add_table(rows=11, cols=4)
    api_table.columns[0].width = Inches(0.9)
    api_table.columns[1].width = Inches(2.4)
    api_table.columns[2].width = Inches(1.2)
    api_table.columns[3].width = Inches(2.0)
    
    api_rows = [
        ("Method", "Endpoint Path", "الصلاحية / Auth", "الوظيفة / Purpose"),
        ("GET", "/api/v1/system", "Public", "عرض نمط التشغيل (Academy vs Demo) ومصدر البيانات"),
        ("POST", "/api/v1/chat", "Public", "الاستفسار عن الكورسات المعتمدة واسترجاع إجابات موثقة"),
        ("POST", "/api/v1/qualification", "Public", "بدء وإدارة جلسة تأهيل واختيار الكورس المناسب للمتدرب"),
        ("POST", "/api/v1/leads", "Public", "تسجيل بيانات الطالب المهتم بعد موافقته الصريحة"),
        ("GET", "/api/v1/catalog/courses", "Public", "استعراض الكورسات المنشورة للطلاب والجمهور"),
        ("POST", "/api/v1/catalog/uploads", "Staff Key", "رفع ملف كورس جديد وبدء عملية التدقيق والتقطيع"),
        ("POST", "/api/v1/catalog/approvals", "Staff Key", "اعتماد ونشر كورس في قاعدة المتجهات والكتالوج"),
        ("POST", "/api/v1/catalog/rejections", "Staff Key", "رفض كورس غير مكتمل مع توثيق الأسباب والملاحظات"),
        ("GET / POST", "/api/v1/rfp/opportunities", "Staff Key", "استعراض وتحليل وتحديث فرص المناقصات والعطاءات"),
        ("GET / POST", "/api/v1/curriculum/*", "Staff Key", "أبحاث المناهج، التوليد، مصفوفة الاعتماد، وتصدير PDF"),
    ]
    
    for r_idx, row_vals in enumerate(api_rows):
        for c_idx, val in enumerate(row_vals):
            api_table.rows[r_idx].cells[c_idx].paragraphs[0].add_run(val)
            
    style_table(api_table, header_bg="1E293B")
    doc.add_paragraph()

    # ==========================================================
    # SECTION 6: FRONTEND PAGES & USER EXPERIENCE
    # ==========================================================
    style_heading_1(doc, "6. دليل صفحات واجهة المستخدم (Streamlit Application Pages)")
    
    add_body_p(
        doc,
        "تم تصميم واجهة المستخدم عبر Streamlit لتوفر تجربة مستخدم سلسة وبديهية، وتضم 9 صفحات متخصصة:"
    )
    
    pages = [
        ("0_Home.py (الرئيسية)", "بوابة الترحيب واستعراض نظرة عامة عن نظام REX AI وأهدافه والوكلاء المتاحين وروابط الوصول السريع."),
        ("1_Course_Catalog.py (كتالوج البرامج)", "صفحة مخصصة للطلاب لاستعراض الكورسات المعتمدة فقط، والبحث الدلالي، وطرح أسئلة والحصول على إجابات موثقة."),
        ("2_RFP_Research.py (أبحاث المناقصات)", "لوحة تحكم وكيل المناقصات؛ استعراض العطاءات، التصفية حسب الدولة والمجال، وفحص درجات التوافق وكراسات الشروط."),
        ("3_Course_Documents.py (مستندات الكورسات)", "استعراض المواد والملفات المعتمدة لكل كورس والاطلاع على التوصيف التدريبي الأصلي."),
        ("4_Course_Approvals.py (اعتماد الكورسات)", "الواجهة المركزية للموظفين؛ رفع ملفات الكورسات، مراجعة المقاطع المستخرجة، فحص التحذيرات، واتخاذ قرار القبول أو الرفض."),
        ("5_Document_Generation.py (توليد المستندات)", "توليد الكتيبات والمقترحات والخطط التدريبية باللغتين العربية والإنجليزية وتصديرها بصيغتي DOCX و PDF."),
        ("6_Learner_Follow_Up.py (متابعة الطلاب)", "سجل بيانات المتدربين والمهتمين الذين أبدوا رغبتهم في التسجيل للتواصل معهم من قبل إدارة القبول."),
        ("7_Demo_Setup.py (إعداد العرض التجريبي)", "واجهة تشغيل نماذج الـ TA Demo، وتغذية النظام بأمثلة اختبارية في بيئة معزولة دون المساس ببيانات الأكاديمية."),
        ("8_Curriculum_Agent.py (وكيل المناهج والاعتمادات)", "واجهة بناء المناهج الذكية؛ أبحاث المواضيع، صياغة أهداف بلوم، تطبيق مصفوفات الاعتماد (NCAAA/ABET/TVTC/QQA/Pearson)، وتنزيل التقرير النهائي بصيغة PDF."),
    ]
    
    for title, desc in pages:
        add_bullet(doc, title, desc)
        
    doc.add_paragraph()

    # ==========================================================
    # SECTION 7: TESTING & QUALITY ASSURANCE
    # ==========================================================
    style_heading_1(doc, "7. تقرير ضمان الجودة والاختبارات الآلية (Quality Assurance & Test Audit)")
    
    add_body_p(
        doc,
        "خضع نظام REX AI لفحص برمجي شامل وصارم للتأكد من خلوه من الأخطاء البرمجية واستقراره التشغيلي. "
        "تضمنت حزمة الاختبارات أكثر من 370 اختباراً آلياً غطت جميع المكونات الحساسة:"
    )
    
    qa_table = doc.add_table(rows=6, cols=3)
    qa_table.columns[0].width = Inches(2.2)
    qa_table.columns[1].width = Inches(1.8)
    qa_table.columns[2].width = Inches(2.5)
    
    qa_rows = [
        ("حزمة الاختبارات / Test Suite", "النتيجة / Status", "نطاق الفحص / Scope"),
        ("اختبارات النواة العامة (tests/)", "208 Passed (100%)", "التحقق من تحميل PDF, DOCX, التقطيع, RAG, وحفظ بيانات الطلاب"),
        ("اختبارات وكيل المناقصات (rfp/tests/)", "162 Passed (100%)", "التحقق من زحف المناقصات، التقييم، التنبيهات، وقواعد البيانات"),
        ("اختبارات الربط والتكامل (Integration)", "Passed", "التأكد من توافق FastAPI مع التوجيهات وحماية مفتاح الإدارة X-API-Key"),
        ("اختبارات عدم الهلوسة والاعتماد", "Passed", "ضمان عدم ظهور أي كورس غير معتمد في إجابات الطلاب والبحث"),
        ("الإجمالي الكلي (Total Test Result)", "370 Passed, 0 Failed", "نسبة نجاح 100% لكافة الاختبارات البرمجية للمشروع"),
    ]
    
    for r_idx, row_vals in enumerate(qa_rows):
        for c_idx, val in enumerate(row_vals):
            qa_table.rows[r_idx].cells[c_idx].paragraphs[0].add_run(val)
            
    style_table(qa_table, header_bg="166534") # Forest Green
    doc.add_paragraph()

    # ==========================================================
    # SECTION 8: HOW TO RUN & OPERATE
    # ==========================================================
    style_heading_1(doc, "8. دليل التشغيل والبدء السريع (Quickstart & Execution Guide)")
    
    add_body_p(
        doc,
        "لتشغيل المشروع محلياً، تم تجهيز السيرفرات لتعمل بتوافق كامل عبر الخطوات البسيطة التالية:"
    )
    
    add_bullet(doc, "الخطوة 1: ملف الإعدادات البيئية (.env)", 
               "تم إعداد ملف .env في المجلد الرئيسي ويتضمن الإعدادات الافتراضية، ومفتاح المشرف: REX_CATALOG_ADMIN_KEY=rex-staff-secret-2026")
               
    add_bullet(doc, "الخطوة 2: تشغيل الخادم الخلفي (FastAPI Backend)", 
               "يتم تشغيل السيرفر على العنوان http://127.0.0.1:8000 عبر الأمر:\n"
               "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000")
               
    add_bullet(doc, "الخطوة 3: تشغيل الواجهة الأمامية (Streamlit Frontend)", 
               "في نافذة طرفية أخرى، يتم تشغيل الواجهة على المنفذ 8501 عبر الأمر:\n"
               "python -m streamlit run frontend/app.py")
               
    add_bullet(doc, "الخطوة 4: تشغيل العرض التوضيحي الموجه (Guided TA Demo)", 
               "إذا رغبت في تشغيل بيئة العرض التوضيحي المخصصة للمناقشة المستقلة على المنافذ 8010 و 8510:\n"
               "python scripts/run_demo.py")

    # ==========================================================
    # SIGN-OFF & CONCLUSION
    # ==========================================================
    doc.add_paragraph()
    add_callout(
        doc,
        "تم بحمد الله إعداد هذا التوثيق الشامل ومراجعة كود وبنية مشروع REX AI لأكاديمية أندلسية. "
        "النظام جاهز ومفحوص بالكامل لتقديمه في مناقشة مشاريع التخرج وعرضه أمام لجنة التقييم بكل ثقة واحترافية.",
        title="خاتمة واعتماد التسليم (Project Sign-off)"
    )
    
    out_path = Path(r"c:\Users\HP\Desktop\Fares\Andalusia\Final Project test\REX_AI\REX_AI_Project_Documentation.docx")
    doc.save(str(out_path))
    print(f"Document successfully created at: {out_path}")

if __name__ == "__main__":
    build_document()
