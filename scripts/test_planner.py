"""
End-to-end test of the Phase 3 AI Planner.
Run: python scripts/test_planner.py
"""
import sys, json
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from backend.app.services.ai_planner import AIPlannerService, PlannerRequest

TEST_CASES = [
    ("Every morning send weather and AI news to my email",
     "Full scheduled workflow with email delivery"),
    ("Fetch GitHub stats for microsoft/vscode and post to Slack",
     "GitHub + Slack, manual trigger"),
    ("Send",
     "Too short — should need clarification"),
    ("Get USD to INR exchange rates daily",
     "Currency + schedule, no email = dashboard only"),
    ("Generate a LeetCode progress report for my class every Monday and email it",
     "LeetCode + schedule + email delivery"),
]

print("=" * 70)
print("Phase 3 AI Planner — End-to-End Test")
print("=" * 70)

all_pass = True

for text, label in TEST_CASES:
    print(f"\n[{label}]")
    print(f"Input: {text!r}")

    req = PlannerRequest(request_text=text)
    resp = AIPlannerService.plan(req)

    if resp.status == "error":
        print(f"  ERROR: {resp.error_message}")
        all_pass = False
        continue

    plan = resp.plan
    if not plan:
        print("  ERROR: No plan returned")
        all_pass = False
        continue

    print(f"  Status          : {resp.status}")
    print(f"  Workflow name   : {plan.workflow_name}")
    print(f"  Confidence      : {plan.confidence_score} ({plan.confidence_label})")
    print(f"  Trigger         : {plan.trigger.type} | cron={plan.trigger.cron} | {plan.trigger.schedule_label}")
    print(f"  Steps ({len(plan.steps)}):")
    for s in plan.steps:
        print(f"    {s.step_number}. [{s.action}] {s.name} — {s.explanation[:60]}")
    print(f"  Integrations    : {plan.integrations}")
    print(f"  Channels        : {plan.channels}")
    print(f"  Missing info    : {len(plan.missing_info)}")
    for m in plan.missing_info:
        print(f"    • {m.field}: {m.question[:60]}")
    print(f"  Needs clarif.   : {plan.needs_clarification}")
    if plan.clarification_question:
        print(f"  Question        : {plan.clarification_question}")
    print(f"  Fallback used   : {plan.fallback_used}")
    print(f"  Explanation     : {plan.explanation[:120]}...")

    # Assertions
    assert plan.workflow_name, "workflow_name must not be empty"
    assert 0.0 <= plan.confidence_score <= 1.0, "confidence_score must be 0-1"
    assert plan.confidence_label in ("high", "medium", "low"), "invalid confidence_label"
    assert len(plan.steps) >= 1, "must have at least 1 step"
    assert len(plan.channels) >= 1, "must have at least 1 channel"
    assert plan.trigger.type in ("manual", "schedule", "webhook", "event")
    print("  PASS ✓")

print()
print("=" * 70)
print(f"All tests {'PASSED ✓' if all_pass else 'FAILED ✗'}")
print("=" * 70)

# Test multi-turn clarification
print("\n[Multi-turn clarification test]")
import uuid
session_id = str(uuid.uuid4())

req1 = PlannerRequest(request_text="send weather", session_id=session_id)
resp1 = AIPlannerService.plan(req1)
print(f"Turn 1 status: {resp1.status}")
if resp1.status == "needs_clarification":
    print(f"Question: {resp1.question}")
    history = AIPlannerService.get_session_history(session_id)
    print(f"Session turns: {len(history)}")
    assert len(history) > 0, "Session should have history"

    req2 = PlannerRequest(
        request_text="send weather for Chennai to my email daily",
        session_id=session_id,
        conversation_history=history,
    )
    resp2 = AIPlannerService.plan(req2)
    print(f"Turn 2 status: {resp2.status}")
    if resp2.plan:
        print(f"Turn 2 plan: {resp2.plan.workflow_name} | confidence={resp2.plan.confidence_score}")
    print("Multi-turn PASS ✓")

AIPlannerService.clear_session(session_id)
print("Session cleared ✓")
print("\nAll planner tests complete.")
