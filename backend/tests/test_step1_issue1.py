"""
Test Suite: Step 1 - Issue 1.1 Verification
Focus: Strict JWT Authentication Enforcement & Zero Silent User 1 Fallback.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import HTTPException
from main import list_all_jobs, get_candidate_profile
from app.core.security import get_current_user, get_optional_current_user, create_access_token
from app.db.session import SessionLocal
from app.db.models import User

def test_issue_1_1():
    print("=" * 65)
    print("🚀 RUNNING STEP 1 - ISSUE 1.1: STRICT AUTHENTICATION ENFORCEMENT")
    print("=" * 65)

    db = SessionLocal()
    try:
        # 1. Test get_optional_current_user without token returns None (Zero fallback to User 1)
        no_token_user = get_optional_current_user(token=None, db=db)
        assert no_token_user is None, f"FAIL: get_optional_current_user returned {no_token_user} instead of None!"
        print("✅ 1. get_optional_current_user(None) == None (Zero silent fallback to User 1).")

        # 2. Test get_current_user without token raises HTTP 401 Unauthorized
        try:
            get_current_user(token=None, db=db)
            assert False, "FAIL: get_current_user(None) did not raise 401!"
        except HTTPException as e:
            assert e.status_code == 401, f"Expected 401, got {e.status_code}"
            print("✅ 2. get_current_user(None) strictly raises HTTP 401 Unauthorized.")

        # 3. Test invalid JWT token raises HTTP 401 Unauthorized
        try:
            get_current_user(token="invalid_tampered_token_string", db=db)
            assert False, "FAIL: Tampered token did not raise 401!"
        except HTTPException as e:
            assert e.status_code == 401
            print("✅ 3. Invalid/tampered token strictly raises HTTP 401 Unauthorized.")

        # 4. Ensure User 2 exists in database for testing
        u2 = db.query(User).filter(User.id == 2).first()
        if not u2:
            from app.core.security import hash_password
            u2 = User(
                id=2,
                email="candidate2@autojob.ai",
                password_hash=hash_password("TestPass123!"),
                full_name="Candidate Two",
                is_active=True
            )
            db.add(u2)
            db.commit()

        # 5. Test token resolution is strictly scoped
        t1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
        t2 = create_access_token(user_id=2, email="candidate2@autojob.ai")

        u1 = get_current_user(token=t1, db=db)
        u2 = get_current_user(token=t2, db=db)

        assert u1.id == 1 and u1.email == "rayavaramjayasurya@gmail.com"
        assert u2.id == 2 and u2.email == "candidate2@autojob.ai"
        print(f"✅ 4. User tokens resolve strictly to their own accounts (User 1: {u1.id}, User 2: {u2.id}).")

        # 6. Test Profile isolation
        p1 = get_candidate_profile(current_user=u1)
        p2 = get_candidate_profile(current_user=u2)
        assert p1.personal_info.name == "Rayavaram Jayasurya"
        assert p2.personal_info.name == "Candidate Two"
        print("✅ 5. Route get_candidate_profile isolates User 1 vs User 2 profiles.")

        # 7. Test Jobs isolation
        j1 = list_all_jobs(db=db, current_user=u1, status_filter=None, days_limit=7)
        j2 = list_all_jobs(db=db, current_user=u2, status_filter=None, days_limit=7)
        assert len(j2) == 0, f"FAIL: User 2 saw {len(j2)} jobs, expected 0 (leakage from User 1)!"
        print(f"✅ 6. Route list_all_jobs enforces tenant boundaries: User 1 ({len(j1)} jobs), User 2 ({len(j2)} jobs).")

        print("\n" + "=" * 65)
        print("🎉 ALL 6 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.1!")
        print("=" * 65)

    finally:
        db.close()

if __name__ == "__main__":
    test_issue_1_1()
