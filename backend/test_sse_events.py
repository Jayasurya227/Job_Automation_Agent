"""
Module: test_sse_events.py
Purpose: Step 5.1 Verification Suite - Tests EventBus Pub/Sub, FastAPI SSE streaming,
         and real-time event broadcasting during LangGraph workflows and Job Discovery.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 5 (Production Reliability).
"""
import sys
import json
import time
import asyncio
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.utils.event_bus import EventBus, emit_event, event_bus
from app.db.session import init_db
from app.agent.workflow import run_application_workflow
from fastapi.testclient import TestClient
from main import app

def run_tests():
    init_db()
    print("\n=======================================================", flush=True)
    print("  STEP 5.1 REAL-TIME SERVER-SENT EVENTS (SSE) SUITE", flush=True)
    print("=======================================================", flush=True)

    # -------------------------------------------------------------
    # TEST 1: EventBus Topic Subscription & Publishing
    # -------------------------------------------------------------
    print("\n[TEST 1/4] Verifying Async EventBus Topic Subscription & Delivery...", flush=True)
    
    async def test_bus_async():
        bus = EventBus(history_limit=10)
        q_topic = await bus.subscribe("workflow:test_1")
        q_all = await bus.subscribe("all")

        test_payload = {"step": "evaluate", "status": "running", "message": "Evaluating fit..."}
        bus.publish("workflow:test_1", "workflow_step", test_payload)

        # Topic queue reception
        ev1 = q_topic.get_nowait()
        assert ev1["event"] == "workflow_step"
        assert ev1["data"]["step"] == "evaluate"
        assert ev1["topic"] == "workflow:test_1"

        # Wildcard 'all' queue reception
        ev2 = q_all.get_nowait()
        assert ev2["event"] == "workflow_step"
        assert ev2["data"]["step"] == "evaluate"

        # Unsubscribe cleanup
        await bus.unsubscribe("workflow:test_1", q_topic)
        await bus.unsubscribe("all", q_all)
        assert len(bus._subscribers["workflow:test_1"]) == 0
        assert len(bus._subscribers["all"]) == 0

    asyncio.run(test_bus_async())
    print("  [SUCCESS] EventBus topic routing, wildcard distribution, and queue cleanup verified.", flush=True)

    # -------------------------------------------------------------
    # TEST 2: Rolling History Buffer for Immediate Client Hydration
    # -------------------------------------------------------------
    print("\n[TEST 2/4] Testing EventBus Ring Buffer Cache for Instant Hydration...", flush=True)
    bus2 = EventBus(history_limit=5)
    for i in range(7):
        bus2.publish("workflow:cache_test", "progress", {"count": i})

    recent = bus2.get_recent_events("workflow:cache_test")
    assert len(recent) == 5, f"Expected 5 cached events, got {len(recent)}"
    assert recent[-1]["data"]["count"] == 6
    assert recent[0]["data"]["count"] == 2
    print("  [SUCCESS] Rolling history buffer maintains exact bounds and retains most recent events.", flush=True)

    # -------------------------------------------------------------
    # TEST 3: FastAPI SSE Endpoint (/api/events/stream)
    # -------------------------------------------------------------
    print("\n[TEST 3/4] Testing FastAPI /api/events/stream Endpoint...", flush=True)
    from fastapi import Request
    from main import stream_events

    async def test_sse_endpoint():
        event_bus.publish("test_channel", "ping_event", {"msg": "hello_sse"})
        req = Request(scope={"type": "http", "method": "GET", "path": "/api/events/stream"})
        resp = await stream_events(req, topic="test_channel")
        assert resp.media_type == "text/event-stream"
        assert resp.headers["Cache-Control"] == "no-cache"

        gen = resp.body_iterator
        f1 = await gen.__anext__()
        assert ": connected to topic test_channel" in f1

        f2 = await gen.__anext__()
        assert "event: ping_event" in f2
        assert "hello_sse" in f2
        await gen.aclose()

    asyncio.run(test_sse_endpoint())
    print("  [SUCCESS] FastAPI SSE StreamingResponse returns valid text/event-stream frames.", flush=True)

    # -------------------------------------------------------------
    # TEST 4: Real-Time Event Emission in LangGraph Workflow
    # -------------------------------------------------------------
    print("\n[TEST 4/4] Testing Real-Time Workflow Event Broadcasting...", flush=True)
    
    async def test_workflow_events():
        # Subscribe to workflow events
        received_events = []
        q = await event_bus.subscribe("workflow:all")

        # Run high-match assisted workflow with staged resume artifacts
        wf_res = run_application_workflow(
            job_title="Full Stack AI Engineer",
            company_name="Apex Neural Systems",
            job_description="Seeking a Full Stack AI Engineer with Python, FastAPI, and React experience.",
            job_url="",
            portal_name="LinkedIn Easy Apply",
            match_score=90,
            requires_human_approval=True,
            tailored_resume_tex_path="output/resumes/junior_ai_engineer_resume.tex",
            cold_email_body="Dear Hiring Team, I am excited to apply for the Full Stack AI Engineer position."
        )

        # Collect events emitted during workflow
        while not q.empty():
            received_events.append(q.get_nowait())

        await event_bus.unsubscribe("workflow:all", q)

        steps_emitted = [ev["data"].get("step") for ev in received_events if "data" in ev]
        print(f"  Emitted workflow steps: {steps_emitted}", flush=True)

        assert "start" in steps_emitted or "evaluate" in steps_emitted
        assert "tailor" in steps_emitted
        assert "prepare_form" in steps_emitted
        assert "review_gateway" in steps_emitted

    asyncio.run(test_workflow_events())
    print("  [SUCCESS] LangGraph workflow successfully emitted all life-cycle events over SSE bus.", flush=True)

    print("\n=======================================================", flush=True)
    print("  STEP 5.1 SSE REAL-TIME SYSTEM: ALL 4 TESTS PASSED (100%)", flush=True)
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    run_tests()
