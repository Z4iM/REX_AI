import json

def t(i, title, issuer, country, pub, deadline, category, elig, desc, expected, source_url="auto", **extra):
    rec = {
        "title": title, "issuer": issuer, "country": country,
        "publication_date": pub, "deadline": deadline, "category": category,
        "eligibility": elig, "submission_url": f"https://demo.rex-ai.example/submit/{i:03d}",
        "source_url": f"https://demo.rex-ai.example/tenders/{i:03d}" if source_url == "auto" else source_url,
        "description": desc, "expected_status": expected,   # expected_status is for tests only
    }
    rec.update(extra)
    return rec

D = []
a = D.append
# ---------- Egypt, valid (accepted / high) ----------
a(t(1,"IT Training Program for Government Employees","Ministry of Digital Affairs (Demo)","Egypt","2026-10-01","2026-12-15","IT training","Registered training provider; 3+ years experience","Hands-on IT training for 300 civil servants covering Python, databases and cybersecurity basics.","accepted"))
a(t(2,"Digital Transformation Capacity Building","National Planning Authority (Demo)","مصر","2026-10-05","2026-11-30","Digital Transformation","Company registered in Egypt; trainers with certifications","Capacity building workshops for mid-level managers on digital transformation strategy.","accepted"))
a(t(3,"Corporate Learning Platform and Soft Skills Training","Delta Industrial Group (Demo)","EG","2026-09-28","2026-11-10","Corporate Learning","Past performance in corporate training required","Blended soft skills training for 500 employees including e-learning content.","accepted"))
a(t(4,"تدريب فني للعاملين بالمصانع","هيئة التنمية الصناعية (تجريبي)","جمهورية مصر العربية","2026-10-10","2026-12-01","Technical Training","مزود تدريب معتمد","برنامج تدريب فني وتطوير مهني للعاملين في قطاع الصناعة.","accepted"))
a(t(5,"AI and Data Skills Upskilling Program","Cairo Banking Alliance (Demo)","Egypt","2026-10-12","2026-11-25","Professional Development","Minimum 5 completed corporate programs","Upskilling program in data analysis and AI for 120 bank employees.","accepted"))
a(t(6,"Software Development Bootcamp for Graduates","Egyptian Youth Fund (Demo)","Egypt","2026-10-15","2027-01-20","Software and IT Training","Training center license; Arabic-speaking instructors","Six-month software development training for fresh graduates.","accepted"))
a(t(7,"Teacher Professional Development Workshops","Regional Education Directorate (Demo)","egypt","2026-10-02","2026-10-19","Education and Training","Education sector experience","Workshops on modern teaching methods for school teachers. Deadline is today.","accepted"))
a(t(8,"Training Services Framework Agreement","Suez Logistics Company (Demo)","Egypt","2026-10-14",None,"Corporate Learning","Not specified","Framework agreement for training services. Deadline not announced yet.","needs_review"))
# ---------- Saudi Arabia, valid (accepted / monitor) ----------
a(t(9,"Digital Skills Training for Public Sector","Digital Government Authority (Demo)","Saudi Arabia","2026-10-03","2026-12-20","Digital Transformation","Local registration or local partner required","Digital skills training program for 1,000 public sector employees.","accepted"))
a(t(10,"Cybersecurity Awareness and Technical Training","National Security Training Center (Demo)","KSA","2026-10-08","2026-11-28","Technical Training","ISO-certified provider","Technical training courses for IT teams on cybersecurity operations.","accepted"))
a(t(11,"برنامج تطوير مهني للقيادات","وزارة الموارد البشرية (تجريبي)","المملكة العربية السعودية","2026-10-06","2026-12-10","Professional Development","خبرة سابقة في برامج القيادة","برنامج تطوير مهني وبناء قدرات للقيادات الوسطى.","accepted"))
a(t(12,"E-learning Content Development","Vision Education Company (Demo)","Kingdom of Saudi Arabia","2026-10-11","2026-11-18","Education and Training","Arabic e-learning portfolio","Development of e-learning curriculum and interactive content.","accepted"))
a(t(13,"Cloud Computing Training Program","Eastern Province Utilities (Demo)","السعودية","2026-10-09","2027-01-05","Software and IT Training","Cloud vendor certification preferred","Training program on cloud computing for 200 engineers.","accepted"))
a(t(14,"Corporate Learning Partnership 2027","Gulf Energy Services (Demo)","SA","2026-10-13","2026-12-30","Corporate Learning","Pre-qualification required","Annual corporate learning partnership covering technical and management training.","accepted"))
# ---------- Duplicates (rejected) ----------
a(t(15,"IT Training Program for Government Employees","Ministry of Digital Affairs (Demo)","Egypt","2026-10-01","2026-12-15","IT training","Registered training provider","Same tender found on a second portal.","rejected"))
a(t(16,"  it training program for GOVERNMENT employees ","ministry of digital affairs (demo)","Egypt","2026-10-02","2026-12-15","IT training","Registered training provider","Same tender with different casing and spacing.","rejected"))
a(t(17,"Digital Skills Training for Public Sector","Digital Government Authority (Demo)","Saudi Arabia","2026-10-04","2026-12-20","Digital Transformation","Local registration","Duplicate of the Saudi digital skills tender.","rejected"))
# ---------- Outside supported countries (rejected) ----------
a(t(18,"Corporate Training Services Tender","European Commission Agency (Demo)","Germany","2026-10-01","2026-12-01","Corporate Learning","EU registered company","Training services for EU staff.","rejected"))
a(t(19,"Professional Development Program","State Education Board (Demo)","United States","2026-10-02","2026-11-20","Professional Development","US-based provider","Teacher professional development in the US.","rejected"))
a(t(20,"IT Training for Banking Sector","Emirates Financial Group (Demo)","United Arab Emirates","2026-10-03","2026-12-05","IT training","UAE trade license","IT training for UAE bank staff.","rejected"))
a(t(21,"Vocational Training Initiative","Amman Skills Council (Demo)","Jordan","2026-10-04","2026-11-30","Technical Training","Jordanian company","Vocational training program in Jordan.","rejected"))
a(t(22,"Leadership Training Program","London Training Board (Demo)","United Kingdom","2026-10-05","2026-12-12","Professional Development","UK registered","Leadership training in the UK.","rejected"))
# ---------- Missing country (needs_review) ----------
a(t(23,"Training Services for Technical Staff","Unknown Regional Authority (Demo)",None,"2026-10-07","2026-12-08","Technical Training","Not specified","Country was not stated in the source page.","needs_review"))
a(t(24,"Education Technology Workshops","Regional Council (Demo)","","2026-10-08","2026-11-22","Education and Training","Not specified","Country field is empty.","needs_review"))
# ---------- Expired (rejected) ----------
a(t(25,"IT Training Program for Municipal Staff","Alexandria Governorate (Demo)","Egypt","2026-07-01","2026-09-15","IT training","Registered provider","Deadline has passed.","rejected"))
a(t(26,"Professional Development for Engineers","Riyadh Engineering Authority (Demo)","Saudi Arabia","2026-06-10","2026-08-30","Professional Development","Engineering sector experience","Deadline has passed.","rejected"))
a(t(27,"Training Needs Assessment","Giza Health Authority (Demo)","Egypt","2026-09-01","2026-10-18","Corporate Learning","Not specified","Expired yesterday.","rejected"))
# ---------- Not related to education/training (rejected) ----------
a(t(28,"Road Construction and Maintenance","Ministry of Transport (Demo)","Egypt","2026-10-01","2026-12-20","Construction","Class A contractor","Construction of a 40 km road.","rejected"))
a(t(29,"Supply of Medical Equipment","Riyadh Health Cluster (Demo)","Saudi Arabia","2026-10-02","2026-12-18","Supply","Authorized medical supplier","Supply of imaging devices to hospitals.","rejected"))
a(t(30,"Office Furniture Supply","Cairo Administrative Authority (Demo)","Egypt","2026-10-03","2026-11-15","Supply","Registered supplier","Supply of desks and chairs.","rejected"))
a(t(31,"Security Guard Services","Jeddah Logistics Park (Demo)","KSA","2026-10-04","2026-12-02","Facility services","Security license","Security staffing for a logistics park.","rejected"))

# ---------- NEW edge cases (review findings) ----------
a(t(32,"Leadership Training for Municipal Staff","Riyadh Municipality (Demo)","Riyadh","2026-10-10","2026-12-18","Professional Development","Local provider","Location field holds only a verified Saudi city.","accepted"))
a(t(33,"E-learning Platform Rollout","Alexandria Port Authority (Demo)","Alexandria, Egypt","2026-10-10","2026-12-22","Corporate Learning","Egyptian company","Country given with city.","accepted"))
a(t(34,"Digital Skills Bootcamp","Regional Skills Agency (Demo)","Egypt","2026-10-11","2026-12-28","Digital Transformation","Local","Twin tender - Egypt copy.","accepted"))
a(t(35,"Digital Skills Bootcamp","Regional Skills Agency (Demo)","Saudi Arabia","2026-10-11","2026-12-28","Digital Transformation","Local","Twin tender - Saudi copy: same title, issuer and deadline, DIFFERENT country and URL. Must NOT be a duplicate.","accepted"))
a(t(36,"Technical Training Services","Industrial Zone Authority (Demo)","Industrial Zone 5","2026-10-12","2026-12-12","Technical Training","Not specified","Location text is not a recognizable country or city.","needs_review"))
a(t(37,"Cybersecurity Training Program","Ministry of Interior Affairs (Demo)","Egypt","2026-10-12","2026-12-12","IT training","Registered provider","Imported from a spreadsheet row without any URL.","needs_review",source_url=None))
a(t(38,"Soft Skills Training Program","Joint Gulf-Nile Council (Demo)","Egypt, Germany","2026-10-12","2026-12-14","Corporate Learning","Not specified","Location names a supported country AND another one.","needs_review"))
a(t(39,"Training of Trainers","Alexandria University Project (Demo)","Alexandria, USA","2026-10-12","2026-12-14","Education and Training","US entity","Alexandria in the United States must not pass as Egypt.","rejected"))
a(t(40,"Teacher Training Reform Program","Education Ministry (Demo)","Egypt","2026-10-13","2026-12-30","Education and Training","Registered provider","Has an official tender number.","accepted",tender_id="EG-EDU-2026-0099"))

import pathlib
with open(pathlib.Path(__file__).parent / "sample_tenders.json", "w", encoding="utf-8") as f:
    json.dump(D, f, ensure_ascii=False, indent=2)
print(len(D), "records written")
