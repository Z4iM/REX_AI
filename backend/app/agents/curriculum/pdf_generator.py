"""Readable curriculum PDF composition sharing the academy document theme."""
from pathlib import Path
from backend.app import runtime
from backend.app.documents.brand import render_pdf

LABELS = {
 'description': ('Description','الوصف'), 'objectives': ('Course objectives','أهداف الدورة'),
 'prerequisites': ('Prerequisites','المتطلبات السابقة'), 'learning_outcomes': ('Learning outcomes','مخرجات التعلم'),
 'modules': ('Modules and learning activities','الوحدات والأنشطة التدريبية'), 'topics': ('Topics','الموضوعات'),
 'activities': ('Learning activities','الأنشطة التدريبية'), 'training_hours': ('Training hours','ساعات التدريب'),
 'duration_hours': ('Duration in hours','المدة بالساعات'), 'target_audience': ('Audience','الجمهور المستهدف'),
 'skill_level': ('Level','المستوى'), 'department': ('Department','القسم'), 'industry': ('Industry','القطاع'),
 'country': ('Country','الدولة'), 'practical_exercises': ('Practical exercises','التمارين العملية'),
 'assessments': ('Assessment plan','خطة التقييم'), 'capstone_project': ('Capstone project','المشروع التطبيقي'),
 'deliverables': ('Deliverables','المخرجات المطلوبة'), 'evaluation_criteria': ('Evaluation criteria','معايير التقييم'),
 'type': ('Type','النوع'), 'module': ('Related module','الوحدة المرتبطة'),
 'weight_percent': ('Weight (%)','الوزن النسبي'), 'summary': ('Analysis summary','ملخص التحليل'),
 'competency_alignment': ('Competency comparison','مقارنة الكفاءات'), 'missing_topics': ('Missing topics','الموضوعات الناقصة'),
 'strengths': ('Strengths','نقاط القوة'), 'recommendations': ('Recommendations','التوصيات'),
}


def generate_curriculum_pdf(curriculum: dict, alignment: dict | None = None) -> bytes:
    c = curriculum
    ar = c.get('language') in ('Arabic','ar')
    def label(key):
        return LABELS.get(key, (key.replace('_',' ').title(), key.replace('_',' ').title()))[1 if ar else 0]
    blocks=[]
    if c.get('description'):
        blocks.append({'kind':'paragraph','text':c['description']})
    rows=[(label(k),str(c[k])) for k in ('training_hours','skill_level','target_audience','department','industry','country') if c.get(k)]
    if rows: blocks.append({'kind':'facts','rows':rows})
    for key in ('objectives','prerequisites','learning_outcomes'):
        blocks.append({'kind':'section','text':label(key)})
        if c.get(key): blocks.append({'kind':'bullets','items':c[key]})
        else: blocks.append({'kind':'paragraph','text':'لم تحدد بيانات إضافية.' if ar else 'No additional information specified.'})
    def item_content(item):
        if item.get('description'): blocks.append({'kind':'paragraph','text':item['description']})
        compact=[(label(k),str(item[k])) for k in ('duration_hours','type','module','weight_percent') if item.get(k) is not None]
        if compact: blocks.append({'kind':'facts','rows':compact})
        for k in ('topics','learning_outcomes','activities','deliverables','evaluation_criteria'):
            if item.get(k):
                blocks.append({'kind':'reference','text':label(k)})
                blocks.append({'kind':'bullets','items':item[k]})
    for key in ('modules','practical_exercises','assessments'):
        blocks.append({'kind':'section','text':label(key)})
        for i,item in enumerate(c.get(key) or [],1):
            blocks.append({'kind':'subheading','text':f'{i:02d}  {item.get("title",label(key))}'})
            item_content(item)
    capstone=c.get('capstone_project') or {}
    if capstone:
        blocks.append({'kind':'section','text':label('capstone_project')})
        blocks.append({'kind':'subheading','text':capstone.get('title',label('capstone_project'))})
        item_content(capstone)
    if alignment:
        blocks.append({'kind':'section','text':'مقارنة مقترحة بمعايير الاعتماد' if ar else 'Proposed accreditation alignment'})
        blocks.append({'kind':'callout','text':'هذا تحليل مقترح فقط ولا يمنح اعتماداً رسمياً.' if ar else 'Proposed alignment analysis only. This does not confer official accreditation.'})
        blocks.append({'kind':'facts','rows':[(('الإطار' if ar else 'Framework'),alignment.get('framework_name','')),
            (('درجة المواءمة' if ar else 'Alignment score'),str(alignment.get('overall_alignment_score',''))+'%')]})
        for key in ('summary','missing_topics','strengths','recommendations'):
            if alignment.get(key):
                blocks.append({'kind':'subheading','text':label(key)})
                blocks.append({'kind':'bullets','items':alignment[key]} if isinstance(alignment[key],list) else {'kind':'paragraph','text':alignment[key]})
        for item in alignment.get('competency_alignment',[]):
            blocks.append({'kind':'subheading','text':item.get('competency','')})
            blocks.append({'kind':'paragraph','text':'\n'.join(str(item.get(k,'')) for k in ('status','curriculum_coverage','gaps','recommendation'))})
    blocks.append({'kind':'appendix','text':'المصادر وسجل المراجعة' if ar else 'Sources and review history'})
    for source in c.get('source_records',[]):
        blocks.append({'kind':'subheading','text':source.get('title',source['course_id'])})
        blocks.append({'kind':'reference','text':f'{source["course_id"]} | {source["reviewed_at"]}'})
        blocks.append({'kind':'reference','text':'SHA256 '+source['source_sha256']})
    if alignment and alignment.get('framework_snapshot'):
        fw=alignment['framework_snapshot']
        blocks.append({'kind':'subheading','text':fw['name']})
        blocks.append({'kind':'paragraph','text':fw.get('source_excerpt') or ''})
        blocks.append({'kind':'reference','text':f'{fw["url"]}\n{fw["last_updated"]} | {fw.get("reviewed_by","")}'})
    for entry in c.get('revision_history') or []:
        blocks.append({'kind':'reference','text':f'{entry.get("date","")} | {entry.get("action","")}\n{entry.get("note","")}'})
    if c.get('id'): blocks.append({'kind':'reference','text':f'Curriculum #{c["id"]}'})
    return render_pdf(blocks,title=c.get('title','Curriculum'),kind='المنهج التدريبي' if ar else 'Course curriculum',
        status=c.get('status','draft'),demo=runtime.is_demo(),ar=ar,cover_overview=c.get('description',''),
        summary=[('ساعة تدريبية' if ar else 'TRAINING HOURS',str(c.get('training_hours',''))),
                 ('الوحدات' if ar else 'MODULES',str(len(c.get('modules') or []))),
                 ('اللغة' if ar else 'LANGUAGE','العربية' if ar else 'English')])


def save_curriculum_pdf(curriculum, alignment=None, output_dir=None):
    directory=Path(output_dir) if output_dir else runtime.curriculum_dir()/'exports'
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f'curriculum-{int(curriculum["id"])}.pdf'
    path.write_bytes(generate_curriculum_pdf(curriculum,alignment))
    return path
