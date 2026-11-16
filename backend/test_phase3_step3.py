"""
Phase 3 - Step 3 Verification Test Suite
Enterprise Rigor Standards:
1. Multi-Tenant Auto-Pilot Status API: Verifies /api/autopilot/status returns strictly per-user data.
2. Auto-Pilot Toggle API: Verifies /api/autopilot/toggle modifies only target user profile in isolated vault.
3. Task Queue Management APIs: Verifies /api/autopilot/tasks and cancel endpoints enforce strict tenant ownership.
4. SSE Event Stream Anti-Eavesdropping Guard: Verifies clients cannot subscribe to other users' private event channels.
5. Profile Boost API Scoping: Verifies /api/autopilot/boost-profile scopes strictly to current_user.
"""

import sys
import os
import json
from pathlib import Path
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.core.security import create_access_token
from app.core.user_storage import ensure_user_storage, load_user_profile, save_user_profile
from app.db.session import SessionLocal
from app.db.models import User
from app.agent.task_queue import task_queue, TaskStatus


def run_tests():
    print("=" * 70)
    print("🧪 PHASE 3 STEP 3: MULTI-TENANT AUTOPILOT APIS & SSE ISOLATION SUITE")
    print("=" * 70)

    # Initialize vaults
    ensure_user_storage(1)
    ensure_user_storage(2)

    # Ensure User 1 and User 2 exist in DB for authentication
    with SessionLocal() as db:
        u1 = db.query(User).filter(User.id == 1).first()
        if not u1:
            u1 = User(id=1, email="rayavaramjayasurya@gmail.com", password_hash="dummy_hash_1", full_name="Rayavaram Jayasurya", is_active=True)
            db.add(u1)
        u2 = db.query(User).filter(User.id == 2).first()
        if not u2:
            u2 = User(id=2, email="candidate2@autojob.ai", password_hash="dummy_hash_2", full_name="Candidate 2", is_active=True)
            db.add(u2)
        db.commit()

    # Generate cryptographic JWT tokens
    token_u1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
    token_u2 = create_access_token(user_id=2, email="candidate2@autojob.ai")

    headers_u1 = {"Authorization": f"Bearer {token_u1}"}
    headers_u2 = {"Authorization": f"Bearer {token_u2}"}

    client = TestClient(app)

    # -------------------------------------------------------------------------
    # TEST 1: /api/autopilot/status Scoped per User
    # -------------------------------------------------------------------------
    print("\n[Test 1] Testing /api/autopilot/status per-user scoping...")
    res1 = client.get("/api/autopilot/status", headers=headers_u1)
    res2 = client.get("/api/autopilot/status", headers=headers_u2)

    assert res1.status_code == 200
    assert res2.status_code == 200

    data1 = res1.json()
    data2 = res2.json()

    assert data1["user_id"] == 1
    assert data2["user_id"] == 2
    assert data1["timeline"]["current_portal"] == "naukri"
    assert data2["timeline"]["current_portal"] == "naukri"
    print(f"  ✅ User 1 Status API: user_id={data1['user_id']} | portal={data1['timeline']['current_portal']}")
    print(f"  ✅ User 2 Status API: user_id={data2['user_id']} | portal={data2['timeline']['current_portal']}")

    # -------------------------------------------------------------------------
    # TEST 2: /api/autopilot/toggle Scoped per User
    # -------------------------------------------------------------------------
    print("\n[Test 2] Testing /api/autopilot/toggle atomic vault isolation...")
    initial_p1_state = getattr(load_user_profile(1).preferences, "autopilot_enabled", False)
    initial_p2_state = getattr(load_user_profile(2).preferences, "autopilot_enabled", False)

    # Toggle User 2
    res_toggle = client.post("/api/autopilot/toggle", headers=headers_u2)
    assert res_toggle.status_code == 200
    toggled_data = res_toggle.json()
    assert toggled_data["user_id"] == 2
    assert toggled_data["autopilot_enabled"] == (not initial_p2_state)

    # Verify User 1 was 100% untouched!
    current_p1_state = getattr(load_user_profile(1).preferences, "autopilot_enabled", False)
    assert current_p1_state == initial_p1_state, "Security Breach: User 1 profile modified when User 2 toggled!"

    # Revert User 2 toggle for cleanup
    client.post("/api/autopilot/toggle", headers=headers_u2)
    print("  ✅ User 2 AutoPilot successfully toggled in private vault.")
    print("  ✅ User 1 vault verified 100% UNTOUCHED.")

    # -------------------------------------------------------------------------
    # TEST 3: /api/autopilot/tasks & Cancel Strict Tenant Ownership
    # -------------------------------------------------------------------------
    print("\n[Test 3] Testing Task Queue APIs & Anti-Tampering Cancellation...")
    import asyncio
    # Enqueue a task for User 2 directly in task queue
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    task_u2 = loop.run_until_complete(task_queue.enqueue_task(
        user_id=2,
        task_type="test_bg_task",
        payload={"param": "user2_val"}
    ))

    # User 2 lists tasks -> sees task_u2
    res_u2_tasks = client.get("/api/autopilot/tasks", headers=headers_u2)
    assert res_u2_tasks.status_code == 200
    u2_task_ids = [t["task_id"] for t in res_u2_tasks.json()]
    assert task_u2.task_id in u2_task_ids

    # User 1 lists tasks -> MUST NOT see task_u2
    res_u1_tasks = client.get("/api/autopilot/tasks", headers=headers_u1)
    assert res_u1_tasks.status_code == 200
    u1_task_ids = [t["task_id"] for t in res_u1_tasks.json()]
    assert task_u2.task_id not in u1_task_ids
    print(f"  ✅ Task List Isolation: User 1 cannot see User 2's task ({task_u2.task_id})")

    # User 1 attempts to cancel User 2's task -> 400 Access Denied
    res_cancel_breach = client.post(f"/api/autopilot/tasks/{task_u2.task_id}/cancel", headers=headers_u1)
    assert res_cancel_breach.status_code == 400
    print("  ✅ Anti-Tampering Check Passed: User 1 cannot cancel User 2's task.")

    # User 2 cancels User 2's own task -> 200 OK
    res_cancel_own = client.post(f"/api/autopilot/tasks/{task_u2.task_id}/cancel", headers=headers_u2)
    assert res_cancel_own.status_code == 200
    assert res_cancel_own.json()["status"] == "cancelled"
    print("  ✅ User 2 successfully cancelled their own task.")

    # -------------------------------------------------------------------------
    # TEST 4: SSE Event Stream Anti-Eavesdropping Guard
    # -------------------------------------------------------------------------
    print("\n[Test 4] Testing SSE Event Stream Anti-Eavesdropping Guard...")

    # Scenario A: Unauthenticated client tries to listen to private user channel
    res_unauth = client.get("/api/events/stream?topic=autopilot:2")
    assert res_unauth.status_code == 401
    print("  ✅ SSE Guard Passed: Unauthenticated client blocked with HTTP 401.")

    # Scenario B: User 1 tries to eavesdrop on User 2's private channel
    res_eavesdrop = client.get("/api/events/stream?topic=autopilot:2", headers=headers_u1)
    assert res_eavesdrop.status_code == 403
    print("  ✅ SSE Guard Passed: Cross-tenant eavesdropping blocked with HTTP 403 Forbidden.")

    # Scenario C: User 2 listens to User 2's own channel -> Permitted (Handshake returned)
    from fastapi import Request
    from main import stream_events
    async def verify_sse_authorized():
        req = Request(scope={"type": "http", "method": "GET", "path": "/api/events/stream", "headers": [(b"authorization", f"Bearer {token_u2}".encode())]})
        resp = await stream_events(req, topic="autopilot:2", token=token_u2)
        assert resp.media_type == "text/event-stream"
        gen = resp.body_iterator
        first_chunk = await gen.__anext__()
        assert "connected to topic autopilot:2" in first_chunk
        await gen.aclose()
    loop.run_until_complete(verify_sse_authorized())
    print("  ✅ SSE Guard Passed: Authorized client successfully connected to private stream.")

    # -------------------------------------------------------------------------
    # TEST 5: /api/autopilot/boost-profile Scoped per User
    # -------------------------------------------------------------------------
    print("\n[Test 5] Testing /api/autopilot/boost-profile per-user resolution...")
    # User 2 has no Naukri session yet, so it should safely return unconfigured warning for User 2
    res_boost_u2 = client.post("/api/autopilot/boost-profile", headers=headers_u2)
    assert res_boost_u2.status_code == 200
    boost_data2 = res_boost_u2.json()
    assert boost_data2.get("status") == "error"
    assert "User 2" in boost_data2.get("message", "")
    print(f"  ✅ Profile Boost API safely scoped to User 2: {boost_data2.get('message')}")

    print("\n" + "=" * 70)
    print("🎉 ALL PHASE 3 STEP 3 TESTS PASSED WITH 100% ACCURACY & SECURITY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
