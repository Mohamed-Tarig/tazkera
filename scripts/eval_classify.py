"""
Tazkera — Classification Evaluation Script

Runs the AI classifier on a sample of tickets with known labels
and measures accuracy, per-class performance, and routing correctness.
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.database import async_session
from src.models.ticket import Ticket
from src.services.classifier import classify_ticket

# ── Config ──
SAMPLE_SIZE = 50  # Number of tickets to evaluate (costs ~$0.50)
DOMAIN_ID = "sfda"

# ── Ground truth routing rules (from sfda.yaml) ──
EXPECTED_ROUTING = {
    "clearance_objection": {"department": "clearance", "min_priority": "high"},
    "complaint": {"department": ["inspection", "consumer_complaints", "labs"], "min_priority": "medium"},
    "inquiry": {"department": ["registration", "labs"], "min_priority": "low"},
    "meeting_request": {"department": None, "min_priority": "low"},
    "review_request": {"department": "clearance", "min_priority": "medium"},
}

PRIORITY_ORDER = {"low": 0, "medium": 1, "high": 2, "urgent": 3}


def priority_adequate(predicted: str, minimum: str) -> bool:
    """Check if predicted priority meets the minimum threshold."""
    return PRIORITY_ORDER.get(predicted, 0) >= PRIORITY_ORDER.get(minimum, 0)


def department_correct(predicted: str, expected) -> bool:
    """Check if predicted department matches expected (single or list)."""
    if expected is None:
        return True  # No specific department expected
    if isinstance(expected, list):
        return predicted in expected
    return predicted == expected


async def run_eval():
    print("=" * 60)
    print("  Tazkera — Classification Evaluation")
    print("=" * 60)

    async with async_session() as session:
        # Get tickets with known request_type in custom_fields
        result = await session.execute(
            select(Ticket)
            .where(
                Ticket.domain_id == DOMAIN_ID,
                Ticket.source_system == "seed",
            )
            .limit(SAMPLE_SIZE)
        )
        tickets = result.scalars().all()

    if not tickets:
        print("No seed tickets found. Run seed_db.py first.")
        return

    print(f"\nEvaluating {len(tickets)} tickets...")
    print("-" * 60)

    # ── Metrics containers ──
    type_correct = 0
    dept_correct = 0
    priority_adequate_count = 0
    total = 0
    errors = 0

    per_class = defaultdict(lambda: {"total": 0, "type_correct": 0, "dept_correct": 0})
    confidence_scores = []
    latencies = []

    for i, ticket in enumerate(tickets, 1):
        ground_truth_type = ticket.custom_fields.get("request_type")
        if not ground_truth_type:
            continue

        total += 1
        expected = EXPECTED_ROUTING.get(ground_truth_type, {})

        # ── Classify ──
        start = time.time()
        try:
            result = classify_ticket(
                subject=ticket.subject,
                description=ticket.description,
                custom_fields=ticket.custom_fields,
                domain_id=DOMAIN_ID,
            )
        except Exception as e:
            print(f"  [{i}/{len(tickets)}] ERROR: {e}")
            errors += 1
            continue
        elapsed = time.time() - start
        latencies.append(elapsed)

        predicted_type = result["request_type"]
        predicted_dept = result["department"]
        predicted_priority = result["priority"]
        confidence = result["confidence"]
        confidence_scores.append(confidence)

        # ── Evaluate ──
        type_match = predicted_type == ground_truth_type
        dept_match = department_correct(predicted_dept, expected.get("department"))
        priority_ok = priority_adequate(predicted_priority, expected.get("min_priority", "low"))

        if type_match:
            type_correct += 1
        if dept_match:
            dept_correct += 1
        if priority_ok:
            priority_adequate_count += 1

        # Per-class tracking
        per_class[ground_truth_type]["total"] += 1
        if type_match:
            per_class[ground_truth_type]["type_correct"] += 1
        if dept_match:
            per_class[ground_truth_type]["dept_correct"] += 1

        # Progress
        status = "✓" if type_match and dept_match else "✗"
        print(
            f"  [{i:3d}/{len(tickets)}] {status}  "
            f"true={ground_truth_type:<22s} pred={predicted_type:<22s} "
            f"dept={predicted_dept:<20s} conf={confidence:.2f}  {elapsed:.1f}s"
        )

    # ── Summary ──
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)

    type_acc = type_correct / total * 100 if total else 0
    dept_acc = dept_correct / total * 100 if total else 0
    priority_acc = priority_adequate_count / total * 100 if total else 0
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print(f"\n  Total evaluated:         {total}")
    print(f"  Errors:                  {errors}")
    print(f"")
    print(f"  Type accuracy:           {type_correct}/{total} ({type_acc:.1f}%)")
    print(f"  Department accuracy:     {dept_correct}/{total} ({dept_acc:.1f}%)")
    print(f"  Priority adequate:       {priority_adequate_count}/{total} ({priority_acc:.1f}%)")
    print(f"  Average confidence:      {avg_confidence:.3f}")
    print(f"  Average latency:         {avg_latency:.2f}s")

    # ── Per-class breakdown ──
    print(f"\n  {'TYPE':<25s} {'COUNT':>6s} {'TYPE ACC':>10s} {'DEPT ACC':>10s}")
    print(f"  {'-'*25} {'-'*6} {'-'*10} {'-'*10}")

    type_ar = {
        "inquiry": "استفسار",
        "complaint": "شكوى",
        "clearance_objection": "اعتراض على فسح",
        "meeting_request": "طلب اجتماع",
        "review_request": "إعادة نظر",
    }

    for cls_name, metrics in sorted(per_class.items()):
        t = metrics["total"]
        ta = metrics["type_correct"] / t * 100 if t else 0
        da = metrics["dept_correct"] / t * 100 if t else 0
        label = f"{cls_name} ({type_ar.get(cls_name, '')})"
        print(f"  {label:<25s} {t:>6d} {ta:>9.1f}% {da:>9.1f}%")

    # ── Save results ──
    results = {
        "total_evaluated": total,
        "errors": errors,
        "type_accuracy": round(type_acc, 1),
        "department_accuracy": round(dept_acc, 1),
        "priority_adequate_pct": round(priority_acc, 1),
        "average_confidence": round(avg_confidence, 3),
        "average_latency_seconds": round(avg_latency, 2),
        "per_class": {
            k: {
                "total": v["total"],
                "type_accuracy": round(v["type_correct"] / v["total"] * 100, 1) if v["total"] else 0,
                "dept_accuracy": round(v["dept_correct"] / v["total"] * 100, 1) if v["total"] else 0,
            }
            for k, v in per_class.items()
        },
    }

    output_path = Path("docs/eval_results.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to {output_path}")

    print("\n" + "=" * 60)
    print(f"  OVERALL SCORE: {type_acc:.0f}% type / {dept_acc:.0f}% dept / {priority_acc:.0f}% priority")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_eval())
