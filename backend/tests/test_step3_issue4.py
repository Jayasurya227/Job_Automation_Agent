import sys
import os
import asyncio
from pathlib import Path
from starlette.requests import Request

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.core.security import create_access_token
from app.utils.event_bus import event_bus, emit_event
from main import stream_events

def run_tests():
    print("==================================================================")
    print("STEP 3 - ISSUE 3.4 (BUG 18): SSE TOKEN SECURITY & TENANT ISOLATION")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()

        token_u1 = create_access_token(user_id=1, email=u1.email)
        token_u2 = create_access_token(user_id=2, email=u2.email)

        def make_mock_request(auth_header: str = ""):
            scope = {
                "type": "http",
                "method": "GET",
                "headers": [(b"authorization", auth_header.encode())] if auth_header else [],
            }
            return Request(scope)

        # -------------------------------------------------------------
        # TEST 1: Unauthenticated request to private channels -> 401
        # -------------------------------------------------------------
        print("\n--- Test 1: Unauthenticated Private Channel Subscription Guard ---")
        req_anon = make_mock_request()
        
        # Test autopilot:2
        res1 = asyncio.run(stream_events(request=req_anon, topic="autopilot:2"))
        assert res1.status_code == 401, f"Expected 401, got {res1.status_code}"
        
        # Test discovery:2
        res2 = asyncio.run(stream_events(request=req_anon, topic="discovery:2"))
        assert res2.status_code == 401, f"Expected 401 for discovery:2, got {res2.status_code}"
        
        # Test task:2
        res3 = asyncio.run(stream_events(request=req_anon, topic="task:2"))
        assert res3.status_code == 401, f"Expected 401 for task:2, got {res3.status_code}"
        print("  [PASS] Unauthenticated access to private channels strictly rejected with HTTP 401.")

        # -------------------------------------------------------------
        # TEST 2: Cross-Tenant Eavesdropping Guard -> 403 Forbidden
        # -------------------------------------------------------------
        print("\n--- Test 2: Cross-Tenant Eavesdropping Guard ---")
        req_u1 = make_mock_request(auth_header=f"Bearer {token_u1}")
        
        # User 1 tries to snoop on User 2's discovery
        res_snoop_disc = asyncio.run(stream_events(request=req_u1, topic="discovery:2"))
        assert res_snoop_disc.status_code == 403, f"Expected 403 Forbidden, got {res_snoop_disc.status_code}"

        # User 1 tries to snoop on User 2's autopilot
        res_snoop_auto = asyncio.run(stream_events(request=req_u1, topic="autopilot:2"))
        assert res_snoop_auto.status_code == 403, f"Expected 403 Forbidden, got {res_snoop_auto.status_code}"

        # User 1 tries to snoop on User 2's tasks
        res_snoop_task = asyncio.run(stream_events(request=req_u1, topic="task:2"))
        assert res_snoop_task.status_code == 403, f"Expected 403 Forbidden, got {res_snoop_task.status_code}"
        print("  [PASS] User 1 strictly blocked with HTTP 403 from snooping on User 2's private streams.")

        # -------------------------------------------------------------
        # TEST 3: Authorized User Subscribes to Own Channel -> 200 OK
        # -------------------------------------------------------------
        print("\n--- Test 3: Authorized User Access to Own Stream ---")
        req_u2 = make_mock_request(auth_header=f"Bearer {token_u2}")
        res_u2_own = asyncio.run(stream_events(request=req_u2, topic="discovery:2"))
        assert res_u2_own.status_code == 200, f"Expected 200 OK, got {res_u2_own.status_code}"
        print("  [PASS] User 2 successfully authorized for discovery:2 stream.")

        # -------------------------------------------------------------
        # TEST 4: Zero-Leakage: Private events do NOT leak to 'all'
        # -------------------------------------------------------------
        print("\n--- Test 4: Private Channel Zero-Leakage into Global 'all' ---")
        secret_marker = "user2_classified_discovery_payload_999"
        emit_event("discovery:2", "secret_discovery", {"secret": secret_marker, "user_id": 2})

        # Check 'all' history buffer
        all_events = event_bus.get_recent_events("all")
        leaked = any(secret_marker in str(ev) for ev in all_events)
        assert not leaked, "FAIL: Private event leaked into global 'all' stream buffer!"
        print("  [PASS] Private user channel event verified completely absent from global 'all' buffer.")

        # -------------------------------------------------------------
        # TEST 5: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 5: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL CHECKS PASSED FOR STEP 3 - ISSUE 3.4 (BUG 18)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
