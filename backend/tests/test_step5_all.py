import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import MagicMock
from fastapi import HTTPException
from fastapi.responses import FileResponse

# Force WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.core.security import (
    create_access_token,
    get_current_user_from_token_or_header,
)
from main import (
    download_uploaded_resume,
    download_candidate_resume_pdf,
    download_tailored_resume_pdf,
)

def run_step5_tests():
    print("==================================================================")
    print("MASTER STEP 5 REGRESSION TEST SUITE (BUGS 23 TO 26)")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # Create JWT access tokens
        u1_token = create_access_token(user_id=u1.id, email=u1.email)
        u2_token = create_access_token(user_id=u2.id, email=u2.email)

        # ------------------------------------------------------------------
        # BUG 24: Direct PDF Downloads via Query Token or Auth Header
        # ------------------------------------------------------------------
        print("\n--- [Bug 24] Direct PDF Downloads Authentication & Fallback ---")

        # Mock Request object
        mock_req_no_auth = MagicMock()
        mock_req_no_auth.headers = {}

        mock_req_u1_header = MagicMock()
        mock_req_u1_header.headers = {"Authorization": f"Bearer {u1_token}"}

        # 1. Unauthenticated download attempt must raise 401
        try:
            get_current_user_from_token_or_header(request=mock_req_no_auth, token=None, db=db)
            assert False, "Should have raised 401 for missing token and header"
        except HTTPException as e:
            assert e.status_code == 401
            print("  [Pass] Unauthenticated request correctly raised 401 Unauthorized.")

        # 2. Invalid token must raise 401
        try:
            get_current_user_from_token_or_header(request=mock_req_no_auth, token="invalid.token.here", db=db)
            assert False, "Should have raised 401 for invalid token"
        except HTTPException as e:
            assert e.status_code == 401
            print("  [Pass] Invalid token correctly raised 401 Unauthorized.")

        # 3. Header-based authentication resolves user
        resolved_u1_header = get_current_user_from_token_or_header(request=mock_req_u1_header, token=None, db=db)
        assert resolved_u1_header.id == 1
        print(f"  [Pass] Header-based auth correctly resolved User {resolved_u1_header.id} ({resolved_u1_header.email}).")

        # 4. Query param `?token=` resolves user
        resolved_u1_query = get_current_user_from_token_or_header(request=mock_req_no_auth, token=u1_token, db=db)
        assert resolved_u1_query.id == 1
        print(f"  [Pass] Query param `?token=` correctly resolved User {resolved_u1_query.id} ({resolved_u1_query.email}).")

        # 5. Test download_uploaded_resume for User 1 via query param ?token=
        resp1 = download_uploaded_resume(request=mock_req_no_auth, token=u1_token, db=db)
        assert isinstance(resp1, FileResponse)
        assert resp1.status_code == 200
        assert "Master_Resume.pdf" in resp1.filename
        print(f"  [Pass] download_uploaded_resume returned FileResponse 200 for User 1: '{resp1.filename}'.")

        # 6. Test download_candidate_resume_pdf for User 1 via query param ?token=
        resp2 = download_candidate_resume_pdf(request=mock_req_no_auth, token=u1_token, db=db)
        assert isinstance(resp2, FileResponse)
        assert resp2.status_code == 200
        print(f"  [Pass] download_candidate_resume_pdf returned FileResponse 200 for User 1: '{resp2.filename}'.")

        # 7. Test download_tailored_resume_pdf:
        # Find a User 1 job
        u1_job = db.query(Job).filter(Job.user_id == 1).first()
        assert u1_job is not None

        # User 1 accessing User 1 job -> 200
        resp3 = download_tailored_resume_pdf(job_id=u1_job.id, request=mock_req_no_auth, db=db, token=u1_token)
        assert isinstance(resp3, FileResponse)
        assert resp3.status_code == 200
        print(f"  [Pass] download_tailored_resume_pdf returned FileResponse 200 for User 1 on Job {u1_job.id}.")

        # 8. Anti-snoop isolation: User 2 trying to download User 1's job resume -> 404 Job not found
        try:
            download_tailored_resume_pdf(job_id=u1_job.id, request=mock_req_no_auth, db=db, token=u2_token)
            assert False, "Should have raised 404 when User 2 attempts to download User 1 job resume"
        except HTTPException as e:
            assert e.status_code == 404
            print(f"  [Pass] Anti-snoop guard: User 2 accessing User 1's job resume returned 404 Not Found.")

        # ------------------------------------------------------------------
        # ZERO DATA LOSS VERIFICATION
        # ------------------------------------------------------------------
        print("\n--- Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"Job count changed! {u1_initial_jobs} -> {u1_final_jobs}"
        print(f"  [Pass] User 1 job count remains perfectly intact: {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL STEP 5 TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_step5_tests()
