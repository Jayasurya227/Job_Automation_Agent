"""
Module: seed_master_user.py
Purpose: Sub-Step 3: Seeds User #1 (Rayavaram Jayasurya) and backfills all 120 existing
         single-user jobs, applications, and Q&A answers to User #1 with ZERO data loss.
Standards: Rule 1 (Zero Data Loss), Rule 2 (Idempotency), Rule 5 (ACID Compliance).
"""
import json
import bcrypt
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, _DATA_DIR
from app.db.models import User, Job, Application, ApplicationAnswer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed.master")

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "profile.json"

def get_master_user_info():
    """Extracts candidate info from profile.json."""
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            personal = data.get("personal_info", {})
            return {
                "name": personal.get("name", "Rayavaram Jayasurya"),
                "email": personal.get("email", "rayavaramjayasurya@gmail.com").strip().lower(),
            }
    return {
        "name": "Rayavaram Jayasurya",
        "email": "rayavaramjayasurya@gmail.com",
    }

def hash_password(password: str) -> str:
    """Hashes a password using direct bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def seed_master_and_backfill():
    db: Session = SessionLocal()
    try:
        info = get_master_user_info()
        email = info["email"]
        full_name = info["name"]

        # 1. Check or create User #1
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.info(f"Creating Master Account User #1: {full_name} <{email}>...")
            initial_password = "Password@123"
            hashed = hash_password(initial_password)
            user = User(
                id=1,
                email=email,
                full_name=full_name,
                password_hash=hashed,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User #1 successfully created with ID: {user.id}")
        else:
            logger.info(f"User #1 already exists with ID: {user.id}")

        user_id = user.id

        # 2. Backfill jobs
        unlinked_jobs = db.query(Job).filter(Job.user_id.is_(None)).all()
        jobs_count = len(unlinked_jobs)
        if jobs_count > 0:
            logger.info(f"Backfilling {jobs_count} existing jobs to User ID {user_id}...")
            for j in unlinked_jobs:
                j.user_id = user_id
            db.commit()
            logger.info(f"Successfully linked {jobs_count} jobs to User ID {user_id}.")
        else:
            logger.info("All jobs are already linked to a user. Zero unlinked jobs.")

        # 3. Backfill applications
        unlinked_apps = db.query(Application).filter(Application.user_id.is_(None)).all()
        apps_count = len(unlinked_apps)
        if apps_count > 0:
            logger.info(f"Backfilling {apps_count} existing applications to User ID {user_id}...")
            for a in unlinked_apps:
                a.user_id = user_id
            db.commit()
            logger.info(f"Successfully linked {apps_count} applications to User ID {user_id}.")

        # 4. Backfill application answers
        unlinked_answers = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id.is_(None)).all()
        ans_count = len(unlinked_answers)
        if ans_count > 0:
            logger.info(f"Backfilling {ans_count} existing screening answers to User ID {user_id}...")
            for ans in unlinked_answers:
                ans.user_id = user_id
            db.commit()
            logger.info(f"Successfully linked {ans_count} screening answers to User ID {user_id}.")

        # 5. Final Verification
        total_user_jobs = db.query(Job).filter(Job.user_id == user_id).count()
        total_unlinked = db.query(Job).filter(Job.user_id.is_(None)).count()
        logger.info(f"FINAL AUDIT: User #{user_id} ({user.email}) owns {total_user_jobs} jobs. Unlinked jobs: {total_unlinked}.")

    except Exception as e:
        db.rollback()
        logger.error(f"Migration error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_master_and_backfill()
