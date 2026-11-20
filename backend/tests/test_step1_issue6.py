"""
Test Suite: Step 1 - Issue 1.6 Verification
Focus: Master Resume & Profile Lookups & Downloads User Isolation.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import io
import asyncio
from pathlib import Path
from unittest.mock import patch
from fastapi import UploadFile, HTTPException

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.core.user_storage import get_user_resume_path, ensure_user_storage
from main import (
    upload_candidate_resume,
    download_uploaded_resume,
    download_tailored_resume_pdf,
    get_job_detail,
)

async def test_issue_1_6():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUE 1.6: RESUME & PROFILE VAULT ISOLATION", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        ensure_user_storage(1)
        ensure_user_storage(2)

        u1_resume = get_user_resume_path(1)
        u2_resume = get_user_resume_path(2)
        assert u1_resume != u2_resume
        print(f"[PASS] 1. User resume paths are isolated: User 1 -> {u1_resume.name}, User 2 -> {u2_resume.name}", flush=True)

        # 2. Upload dummy resume for User 2
        fake_pdf_content = b"%PDF-1.4\n%Fake PDF content for User 2 unit test\n%%EOF"
        upload_file = UploadFile(
            filename="user2_test_resume.pdf",
            file=io.BytesIO(fake_pdf_content)
        )

        with patch("app.agent.resume_parser.parse_resume_content") as mock_parse:
            from app.schemas.profile import CandidateProfile, PersonalInfo
            mock_profile = CandidateProfile(personal_info=PersonalInfo(name="Candidate Two", email="user2@example.com"))
            mock_parse.return_value = mock_profile

            res = await upload_candidate_resume(file=upload_file, current_user=u2)
            assert res["status"] == "success"
            assert u2_resume.exists()
            assert u2_resume.read_bytes() == fake_pdf_content
            print("[PASS] 2. upload_candidate_resume saves strictly to User 2's vault (Zero cross-contamination).", flush=True)

        # 3. Test download_uploaded_resume isolation
        dl_res_u2 = download_uploaded_resume(inline=False, current_user=u2)
        assert Path(dl_res_u2.path) == u2_resume
        print("[PASS] 3. download_uploaded_resume for User 2 serves User 2's resume.", flush=True)

        # 4. Job detail and tailored resume 404 cross-user guard
        u1_job = db.query(Job).filter(Job.user_id == 1).first()
        assert u1_job is not None

        try:
            get_job_detail(job_id=u1_job.id, db=db, current_user=u2)
            assert False, "FAIL: User 2 was able to view User 1's job details!"
        except HTTPException as e:
            assert e.status_code == 404
            print("[PASS] 4. get_job_detail raises 404 when User 2 attempts to view User 1's job.", flush=True)

        try:
            download_tailored_resume_pdf(job_id=u1_job.id, db=db, inline=False, current_user=u2)
            assert False, "FAIL: User 2 was able to download User 1's job resume!"
        except HTTPException as e:
            assert e.status_code == 404
            print("[PASS] 5. download_tailored_resume_pdf raises 404 when User 2 requests User 1's job resume.", flush=True)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 5 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.6!", flush=True)
        print("=" * 65, flush=True)
    finally:
        # Clean up User 2 test resume
        if u2_resume.exists():
            u2_resume.unlink()
        db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_issue_1_6())
