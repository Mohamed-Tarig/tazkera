import asyncio
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import async_session, engine
from src.models.ticket import Base, KnowledgeBase, Ticket
from src.services.embeddings import content_hash, get_embedding, get_embeddings_batch

# ── Names ──
NAMES = [
    "أحمد الشمري", "سارة القحطاني", "فيصل العتيبي", "نورة المالكي",
    "خالد الدوسري", "ريم الحربي", "عمر الزهراني", "هند البلوي",
    "ماجد السلمي", "دانة الغامدي", "طلال العنزي", "لمياء الرشيدي",
]

CATEGORIES = ["hardware", "software", "network", "email", "access", "printer", "vpn"]
REQUEST_TYPES = ["incident", "service_request", "inquiry", "complaint"]
URGENCIES = ["single_user", "team", "department", "company_wide"]

# ── Ticket Templates ──
TEMPLATES = {
    "incident": [
        {
            "subject": "الجهاز لا يعمل — شاشة زرقاء متكررة",
            "description": "جهازي يعرض شاشة زرقاء بشكل متكرر منذ أمس. حاولت إعادة التشغيل عدة مرات لكن المشكلة تتكرر بعد دقائق من الاستخدام. أحتاج الجهاز بشكل عاجل لإنجاز مشروع مهم.",
            "category": "hardware",
        },
        {
            "subject": "الطابعة لا تطبع — رسالة خطأ Paper Jam",
            "description": "طابعة الطابق الثالث تعرض رسالة Paper Jam رغم عدم وجود ورق عالق. فحصتها يدوياً ولم أجد شيئاً. الطابعة موديل HP LaserJet Pro. الفريق بالكامل متأثر لأنها الطابعة الوحيدة في الطابق.",
            "category": "printer",
        },
        {
            "subject": "انقطاع الإنترنت في مكتب الإدارة المالية",
            "description": "الإنترنت منقطع تماماً في مكتب الإدارة المالية منذ الساعة 9 صباحاً. باقي المكاتب تعمل بشكل طبيعي. حاولنا إعادة تشغيل الراوتر لكن بدون فائدة. 8 موظفين لا يستطيعون العمل.",
            "category": "network",
        },
        {
            "subject": "لا أستطيع الوصول لـ VPN من المنزل",
            "description": "منذ أمس لا أستطيع الاتصال بـ VPN الشركة من المنزل. أحصل على رسالة Connection Timeout. كنت أعمل بشكل طبيعي قبل ذلك. غيّرت كلمة المرور مؤخراً — هل لها علاقة؟",
            "category": "vpn",
        },
        {
            "subject": "البريد الإلكتروني لا يرسل مرفقات كبيرة",
            "description": "لا أستطيع إرسال ملفات أكبر من 5MB عبر البريد. أحصل على رسالة Message Size Exceeded. أحتاج إرسال تقارير PDF كبيرة للعملاء بشكل يومي. هل يمكن رفع الحد الأقصى؟",
            "category": "email",
        },
        {
            "subject": "برنامج ERP يتوقف عن الاستجابة بشكل متكرر",
            "description": "نظام الـ ERP يتجمد عند فتح أكثر من 3 نوافذ. المشكلة تحدث مع كل الموظفين في قسم المحاسبة. الأداء كان ممتازاً قبل التحديث الأخير الأسبوع الماضي.",
            "category": "software",
        },
        {
            "subject": "لوحة المفاتيح لا تعمل بعد انسكاب القهوة",
            "description": "انسكب كوب قهوة على لوحة المفاتيح وتوقفت عن العمل. فصلتها فوراً وجففتها لكن بعض الأزرار لا تستجيب. أحتاج بديل مؤقت لحين إصلاحها أو استبدالها.",
            "category": "hardware",
        },
        {
            "subject": "الشبكة بطيئة جداً في الطابق الثاني",
            "description": "سرعة الإنترنت في الطابق الثاني أصبحت بطيئة جداً هذا الأسبوع. تحميل الملفات يستغرق وقتاً طويلاً واجتماعات Teams تنقطع باستمرار. المشكلة تؤثر على كل الفريق (12 شخص).",
            "category": "network",
        },
        {
            "subject": "لا أستطيع فتح ملفات Excel بعد تحديث Office",
            "description": "بعد تحديث Microsoft Office أمس، ملفات Excel القديمة لا تفتح. تظهر رسالة File Corrupted. جربت ملفات مختلفة ونفس المشكلة. أحتاج هذه الملفات بشكل عاجل.",
            "category": "software",
        },
        {
            "subject": "الكاميرا لا تعمل في اجتماعات Zoom",
            "description": "كاميرا اللابتوب لا تعمل في Zoom و Teams. تظهر شاشة سوداء فقط. جربت المتصفح والتطبيق — نفس المشكلة. التعريفات محدّثة حسب Device Manager.",
            "category": "hardware",
        },
    ],
    "service_request": [
        {
            "subject": "طلب صلاحية وصول لنظام الـ CRM",
            "description": "أنا موظف جديد في قسم المبيعات وأحتاج صلاحية وصول لنظام Salesforce CRM. مديري المباشر أحمد العتيبي وافق على الطلب. أحتاج صلاحيات عرض وتعديل حسابات العملاء.",
            "category": "access",
        },
        {
            "subject": "طلب تثبيت برنامج AutoCAD على جهازي",
            "description": "أحتاج تثبيت AutoCAD 2024 على جهازي للعمل على مشاريع التصميم الهندسي. رقم الترخيص متوفر لدى مدير القسم. الجهاز مواصفاته كافية (16GB RAM, i7).",
            "category": "software",
        },
        {
            "subject": "طلب تجهيز جهاز لابتوب لموظف جديد",
            "description": "سينضم موظف جديد لقسم التسويق يوم الأحد القادم. نحتاج تجهيز لابتوب بالبرامج الأساسية (Office, Teams, Chrome) وإنشاء حساب بريد إلكتروني وحساب Active Directory.",
            "category": "hardware",
        },
        {
            "subject": "طلب إضافة طابعة جديدة للطابق الرابع",
            "description": "مع زيادة عدد الموظفين في الطابق الرابع، نحتاج طابعة إضافية. حالياً 20 موظف يتشاركون طابعة واحدة وهذا يسبب تأخير كبير. نقترح HP LaserJet Enterprise.",
            "category": "printer",
        },
        {
            "subject": "طلب إنشاء قائمة بريدية لفريق المشروع",
            "description": "نحتاج إنشاء قائمة بريدية project-alpha@company.com تضم 15 عضو من أقسام مختلفة. مرفق قائمة الأعضاء. المشروع يبدأ الأسبوع القادم.",
            "category": "email",
        },
        {
            "subject": "طلب رفع صلاحيات المسؤول على الجهاز",
            "description": "أحتاج صلاحيات Admin على جهازي لتثبيت أدوات التطوير (Python, Docker, VS Code). أنا مطوّر في فريق البرمجيات وهذه الأدوات ضرورية لعملي اليومي.",
            "category": "access",
        },
        {
            "subject": "طلب تفعيل حساب VPN للعمل عن بعد",
            "description": "تمت الموافقة على عملي عن بعد يومين في الأسبوع. أحتاج تفعيل حساب VPN وتزويدي بتعليمات الاتصال. مديري سلطان الشمري وافق على الطلب.",
            "category": "vpn",
        },
    ],
    "inquiry": [
        {
            "subject": "استفسار عن سياسة تغيير كلمة المرور",
            "description": "كم مرة يجب تغيير كلمة المرور؟ وما هي المتطلبات (طول، أحرف خاصة)؟ تظهر لي رسالة أن كلمة المرور ستنتهي خلال 5 أيام.",
            "category": "access",
        },
        {
            "subject": "ما هي البرامج المتاحة للتثبيت الذاتي؟",
            "description": "هل توجد قائمة بالبرامج المعتمدة التي يمكنني تثبيتها بنفسي من Software Center؟ أحتاج أدوات تصميم مثل Figma و Canva.",
            "category": "software",
        },
        {
            "subject": "كيف أتصل بالطابعة اللاسلكية؟",
            "description": "نقلت لمكتب جديد وأحتاج معرفة كيفية الاتصال بالطابعة اللاسلكية في الطابق. ما هو اسم الطابعة على الشبكة؟",
            "category": "printer",
        },
        {
            "subject": "هل يمكنني استخدام جهازي الشخصي للعمل؟",
            "description": "هل تسمح سياسة الشركة باستخدام اللابتوب الشخصي للوصول لأنظمة العمل؟ وما هي المتطلبات الأمنية في حال السماح؟",
            "category": "access",
        },
        {
            "subject": "استفسار عن سعة صندوق البريد الإلكتروني",
            "description": "صندوق بريدي شبه ممتلئ. كم السعة القصوى؟ وهل يمكن زيادتها؟ أم يجب أن أحذف رسائل قديمة؟",
            "category": "email",
        },
    ],
    "complaint": [
        {
            "subject": "شكوى من بطء استجابة الدعم الفني",
            "description": "فتحت تذكرة قبل 3 أيام بخصوص مشكلة في جهازي ولم يتواصل معي أحد حتى الآن. رقم التذكرة IT-2024-1234. المشكلة تؤثر على إنتاجيتي بشكل كبير.",
            "category": "hardware",
        },
        {
            "subject": "شكوى من تكرار انقطاع الإنترنت",
            "description": "هذه المرة الرابعة هذا الشهر التي ينقطع فيها الإنترنت في مكتبنا. كل مرة يستغرق الإصلاح ساعات. نحتاج حل جذري وليس ترقيع مؤقت.",
            "category": "network",
        },
        {
            "subject": "شكوى من تحديث إجباري عطّل برنامج مهم",
            "description": "التحديث الإجباري الذي تم أمس عطّل برنامج المحاسبة الذي نستخدمه يومياً. لم يتم إخطارنا مسبقاً. 5 موظفين في القسم المالي لا يستطيعون العمل.",
            "category": "software",
        },
    ],
}

# ── KB Articles ──
KB_ARTICLES = [
    {"title": "سياسة كلمة المرور وأمن الحسابات", "category": "أمن المعلومات", "content": "يجب تغيير كلمة المرور كل 90 يوماً. المتطلبات: 12 حرفاً كحد أدنى، حرف كبير وصغير، رقم، رمز خاص. لا يُسمح بإعادة استخدام آخر 5 كلمات مرور. عند نسيان كلمة المرور، استخدم بوابة الخدمة الذاتية أو تواصل مع مكتب الخدمة."},
    {"title": "كيفية الاتصال بشبكة VPN", "category": "الشبكات", "content": "لتفعيل VPN: 1) حمّل تطبيق FortiClient من Software Center. 2) أدخل عنوان الخادم: vpn.company.com. 3) سجّل دخول ببيانات Active Directory. 4) اختر Two-Factor Authentication عبر تطبيق Microsoft Authenticator. عند وجود مشاكل في الاتصال، تأكد من تحديث التطبيق وأن اتصال الإنترنت لديك مستقر."},
    {"title": "إجراءات طلب جهاز جديد أو بديل", "category": "الأجهزة", "content": "لطلب جهاز جديد: قدّم طلباً عبر بوابة الخدمة مع موافقة المدير المباشر. الأجهزة القياسية تُسلّم خلال 5 أيام عمل. الأجهزة المتخصصة (محطات عمل هندسية، أجهزة تصميم) تستغرق 10-15 يوم عمل. يشمل التجهيز: تثبيت نظام التشغيل، البرامج الأساسية، إعدادات الأمان، والانضمام للنطاق."},
    {"title": "البرامج المعتمدة والتثبيت الذاتي", "category": "البرمجيات", "content": "البرامج المتاحة للتثبيت الذاتي عبر Software Center: Microsoft Office, Google Chrome, Adobe Reader, 7-Zip, Zoom, Teams. البرامج التي تحتاج طلب خاص: AutoCAD, MATLAB, Adobe Creative Suite, Visual Studio. البرامج الممنوعة: أي برنامج غير مرخص، برامج التورنت، أدوات تجاوز الحماية."},
    {"title": "إعداد الطابعات والاتصال بها", "category": "الطابعات", "content": "للاتصال بطابعة: اذهب لـ Settings > Printers > Add Printer. الطابعات المتاحة تظهر تلقائياً على الشبكة. تسمية الطابعات: PRN-[الطابق]-[الرقم] مثل PRN-3-01. عند ظهور Paper Jam: افتح الأبواب الأمامية والخلفية وأزل أي ورق عالق بلطف. لا تستخدم القوة. إذا استمرت المشكلة، افتح تذكرة."},
    {"title": "سياسة BYOD — استخدام الأجهزة الشخصية", "category": "أمن المعلومات", "content": "يُسمح باستخدام الأجهزة الشخصية بشروط: تثبيت برنامج Intune لإدارة الجهاز، تفعيل التشفير، تثبيت مضاد فيروسات معتمد، عدم تخزين بيانات الشركة محلياً. الوصول يكون عبر بوابة الويب أو VPN فقط. الشركة لا تتحمل مسؤولية أعطال الجهاز الشخصي."},
    {"title": "إدارة صندوق البريد الإلكتروني", "category": "البريد الإلكتروني", "content": "سعة صندوق البريد القياسية: 50GB. عند الوصول لـ80% يظهر تنبيه. لتوفير مساحة: احذف الرسائل غير المهمة، أفرغ سلة المحذوفات، انقل المرفقات الكبيرة لـ OneDrive. الحد الأقصى لحجم المرفقات: 25MB. للملفات الأكبر استخدم OneDrive وأرسل رابط مشاركة."},
    {"title": "سياسة التحديثات والصيانة الدورية", "category": "البرمجيات", "content": "التحديثات الأمنية تُثبّت تلقائياً كل ثلاثاء. التحديثات الكبيرة تُجدوَل مسبقاً ويُرسل إشعار قبل 48 ساعة. إذا تعارض تحديث مع برنامج عمل، افتح تذكرة فوراً لاستثناء جهازك مؤقتاً. لا تؤجل التحديثات الأمنية أكثر من 7 أيام."},
    {"title": "إجراءات التعامل مع حوادث أمن المعلومات", "category": "أمن المعلومات", "content": "عند الاشتباه باختراق أو فيروس: 1) افصل الجهاز عن الشبكة فوراً. 2) لا تحاول إصلاح المشكلة بنفسك. 3) اتصل بفريق أمن المعلومات على الرقم الداخلي 5555. 4) لا تحذف أي ملفات. 5) دوّن ما كنت تفعله عند حدوث المشكلة. وقت الاستجابة: 30 دقيقة للحوادث الأمنية."},
    {"title": "طلب صلاحيات ووصول للأنظمة", "category": "الصلاحيات", "content": "لطلب صلاحية: قدّم طلباً عبر بوابة الخدمة مع تحديد النظام المطلوب ونوع الصلاحية (عرض/تعديل/مسؤول). يجب موافقة المدير المباشر ومالك النظام. مدة المعالجة: 2-3 أيام عمل. الصلاحيات تُراجع كل 6 أشهر وتُلغى تلقائياً عند انتهاء العقد أو النقل."},
]


def _ticket_number(index: int) -> str:
    return f"TZK-IT-{index:04d}"


async def seed():
    async with async_session() as session:
        # ── Generate Tickets ──
        tickets = []
        index = 1
        distribution = {"incident": 40, "service_request": 30, "inquiry": 15, "complaint": 15}

        for request_type, count in distribution.items():
            templates = TEMPLATES[request_type]
            for i in range(count):
                template = templates[i % len(templates)]
                name = random.choice(NAMES)

                ticket = Ticket(
                    ticket_number=_ticket_number(index),
                    domain_id="it_helpdesk",
                    source_system="seed",
                    source_ticket_id=f"IT-SEED-{index:04d}",
                    subject=template["subject"],
                    description=template["description"],
                    submitter_name=name,
                    submitter_email=f"{name.replace(' ', '.').lower()}@company.com",
                    custom_fields={
                        "category": template["category"],
                        "request_type": request_type,
                        "urgency": random.choice(URGENCIES),
                    },
                    status="new",
                )
                session.add(ticket)
                tickets.append(ticket)
                index += 1

        print(f"Generated {len(tickets)} IT helpdesk tickets")

        # ── Generate KB Articles ──
        for article in KB_ARTICLES:
            kb = KnowledgeBase(
                domain_id="it_helpdesk",
                title=article["title"],
                content=article["content"],
                category=article["category"],
                is_active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(kb)

        print(f"Generated {len(KB_ARTICLES)} KB articles")
        await session.commit()

        # ── Generate Embeddings for KB ──
        print("Generating KB embeddings...")
        result = await session.execute(
            __import__("sqlalchemy").select(KnowledgeBase).where(
                KnowledgeBase.domain_id == "it_helpdesk",
                KnowledgeBase.embedding.is_(None),
            )
        )
        articles = result.scalars().all()
        texts = [f"{a.title}\n{a.content}" for a in articles]

        for i in range(0, len(texts), 16):
            batch = texts[i:i+16]
            batch_articles = articles[i:i+16]
            embeddings = get_embeddings_batch(batch)
            for article, emb in zip(batch_articles, embeddings):
                article.embedding = emb
            print(f"  KB: {min(i+16, len(texts))}/{len(texts)}")

        await session.commit()

        # ── Generate Embeddings for Tickets ──
        print("Generating ticket embeddings...")
        from sqlalchemy import text as sql_text
        result = await session.execute(
            sql_text("""
                SELECT t.id, t.subject, t.description
                FROM tickets t
                LEFT JOIN ticket_embeddings te ON te.ticket_id = t.id
                WHERE t.domain_id = 'it_helpdesk' AND te.id IS NULL
            """)
        )
        tix = result.fetchall()
        texts = [f"{t.subject}\n{t.description}" for t in tix]

        for i in range(0, len(texts), 16):
            batch = texts[i:i+16]
            batch_tickets = tix[i:i+16]
            embeddings = get_embeddings_batch(batch)
            for ticket, emb in zip(batch_tickets, embeddings):
                await session.execute(
                    sql_text("""
                        INSERT INTO ticket_embeddings (id, ticket_id, embedding, content_hash, created_at)
                        VALUES (:id, :ticket_id, CAST(:embedding AS vector), :hash, NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "ticket_id": str(ticket.id),
                        "embedding": str(emb),
                        "hash": content_hash(f"{ticket.subject}\n{ticket.description}"),
                    },
                )
            print(f"  Tickets: {min(i+16, len(texts))}/{len(texts)}")

        await session.commit()
        print("Done! IT Helpdesk domain seeded.")


if __name__ == "__main__":
    asyncio.run(seed())