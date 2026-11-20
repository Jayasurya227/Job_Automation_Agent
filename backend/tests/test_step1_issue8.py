"""
Test Suite: Step 1 - Issue 1.8 Verification
Focus: Output Snapshots Route Protection, Auth Enforcement & Anti-Snooping Guard.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from fastapi import HTTPException

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.db.models import User
from app.core.user_storage import get_user_snapshots_dir
from app.core.security import create_access_token
from main import get_snapshot_file

def test_issue_1_8():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUE 1.8: SNAPSHOT ROUTE PROTECTION & USER ISOLATION", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    u2_snapshots_dir = get_user_snapshots_dir(2)
    sample_u2_snap = u2_snapshots_dir / "review_user2_test.png"
    sample_u2_snap.write_bytes(b"\x89PNG\r\n\x1a\nFake PNG data for User 2")

    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # 1. Unauthenticated request raises 401 Unauthorized
        try:
            get_snapshot_file("review_user2_test.png", db=db, token=None, current_user=None)
            assert False, "FAIL: Unauthenticated request was allowed!"
        except HTTPException as e:
            assert e.status_code == 401
            print("[PASS] 1. Unauthenticated snapshot request strictly blocked (HTTP 401).", flush=True)

        # 2. Path traversal attack check (e.g., ../../../passwords.txt)
        try:
            get_snapshot_file("../../../secret.png", db=db, token=None, current_user=u1)
            assert False, "FAIL: Path traversal request was allowed!"
        except HTTPException as e:
            assert e.status_code == 400
            print("[PASS] 2. Path traversal attempt strictly blocked (HTTP 400).", flush=True)

        # 3. User 2 can view their own snapshot
        u2_token = create_access_token(user_id=u2.id, email=u2.email)
        res = get_snapshot_file("review_user2_test.png", db=db, token=u2_token, current_user=u2)
        assert Path(res.path) == sample_u2_snap
        print("[PASS] 3. User 2 successfully accesses their own snapshot.", flush=True)

        # 4. Anti-Snooping Guard: User 1 blocked with 403 Forbidden when requesting User 2's snapshot
        try:
            get_snapshot_file("review_user2_test.png", db=db, token=None, current_user=u1)
            assert False, "FAIL: User 1 was allowed to view User 2's snapshot!"
        except HTTPException as e:
            assert e.status_code == 403
            print("[PASS] 4. Anti-Snooping Guard: User 1 blocked from User 2's snapshot (HTTP 403 Forbidden).", flush=True)

        # 5. Nonexistent file returns 404
        try:
            get_snapshot_file("ghost_file_12345.png", db=db, token=None, current_user=u1)
            assert False, "FAIL: Nonexistent file did not return 404!"
        except HTTPException as e:
            assert e.status_code == 404
            print("[PASS] 5. Nonexistent snapshot returns HTTP 404 Not Found.", flush=True)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 5 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.8!", flush=True)
        print("=" * 65, flush=True)
    finally:
        if sample_u2_snap.exists():
            sample_u2_snap.unlink()
        db.close()

if __name__ == "__main__":
    test_issue_1_8()
