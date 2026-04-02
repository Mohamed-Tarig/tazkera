import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.workflows.intake import intake_graph

# A real-looking SFDA ticket
test_ticket = {
    "ticket_id": "test-001",
    "domain_id": "sfda",
    "subject": "اعتراض على رفض فسح شحنة أدوية مستوردة",
    "description": (
        "نعترض على قرار رفض فسح شحنة أموكسيسيلين 250mg الواردة من الهند "
        "ببوليصة شحن رقم BOL-445566. سبب الرفض المذكور هو عدم مطابقة "
        "شهادة التحليل. نرفق شهادة تحليل محدثة من مختبر معتمد ونطلب "
        "إعادة النظر في القرار. رقم الترخيص: IMP-2024-3847."
    ),
    "custom_fields": {
        "establishment_type": "importer",
        "product_type": "drug",
    },
    "classification": {},
    "status": "",
    "error": "",
}

print("Running intake pipeline...\n")
result = intake_graph.invoke(test_ticket)

print(f"Status: {result['status']}")
print(f"Request type: {result['classification'].get('request_type')}")
print(f"Department: {result['classification'].get('department')}")
print(f"Priority: {result['classification'].get('priority')}")
print(f"Confidence: {result['classification'].get('confidence')}")
print(f"Routed by: {result['classification'].get('routed_by')}")
print(f"Reasoning: {result['classification'].get('reasoning')}")