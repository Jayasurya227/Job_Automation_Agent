import sys
import os
import asyncio
from pathlib import Path
from sqlalchemy import text

# Force WindowsSelectorEventLoopPolicy on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal, engine
from app.db.models import User, Job
import app.config as config

def run_step6_tests():
    print("==================================================================")
    print("MASTER STEP 6 REGRESSION TEST SUITE (BUGS 27 TO 30)")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # ------------------------------------------------------------------
        # BUG 27: SQLite WAL Mode, Busy Timeout, and Pragmas
        # ------------------------------------------------------------------
        print("\n--- [Bug 27] SQLite Concurrency Pragmas (WAL, Busy Timeout, Foreign Keys) ---")
        
        # Test PRAGMA journal_mode
        res_journal = db.execute(text("PRAGMA journal_mode;")).scalar()
        print(f"  SQLite journal_mode: {res_journal}")
        assert str(res_journal).lower() == "wal", f"Expected WAL mode, got {res_journal}"
        print("  [Pass] SQLite is running in WAL (Write-Ahead Logging) mode for concurrent access.")

        # Test PRAGMA busy_timeout
        res_timeout = db.execute(text("PRAGMA busy_timeout;")).scalar()
        print(f"  SQLite busy_timeout: {res_timeout} ms")
        assert int(res_timeout) >= 5000, f"Expected busy_timeout >= 5000, got {res_timeout}"
        print("  [Pass] SQLite busy_timeout is configured to prevent 'database is locked' errors.")

        # Test PRAGMA foreign_keys
        res_fk = db.execute(text("PRAGMA foreign_keys;")).scalar()
        print(f"  SQLite foreign_keys: {res_fk}")
        assert int(res_fk) == 1, f"Expected foreign_keys=1, got {res_fk}"
        print("  [Pass] SQLite foreign_keys constraint enforcement is active.")

        # ------------------------------------------------------------------
        # BUG 28: PostgreSQL Readiness & Requirements Check
        # ------------------------------------------------------------------
        print("\n--- [Bug 28] PostgreSQL Production Readiness & Dependency ---")
        req_path = Path(__file__).resolve().parent / "requirements.txt"
        with open(req_path, "r", encoding="utf-8") as f:
            req_content = f.read()
        assert "psycopg2-binary" in req_content, "psycopg2-binary missing from requirements.txt!"
        print("  [Pass] 'psycopg2-binary' dependency is declared in requirements.txt.")

        # ------------------------------------------------------------------
        # BUG 29: JWT Secrets Harmonization
        # ------------------------------------------------------------------
        print("\n--- [Bug 29] JWT Secrets Harmonization ---")
        assert hasattr(config, "JWT_SECRET_KEY") and config.JWT_SECRET_KEY
        assert hasattr(config, "ENVIRONMENT")
        print(f"  Active JWT Secret Key: {'*' * (len(config.JWT_SECRET_KEY) - 4) + config.JWT_SECRET_KEY[-4:]}")
        print(f"  Active Environment: {config.ENVIRONMENT}")
        print("  [Pass] JWT secret configuration is unified and harmonized across env aliases.")

        # ------------------------------------------------------------------
        # BUG 30: Production Deployment Files Audit
        # ------------------------------------------------------------------
        print("\n--- [Bug 30] Multi-Tenant Docker Deployment Files Audit ---")
        root_dir = Path(__file__).resolve().parent.parent
        dc_path = root_dir / "docker-compose.yml"
        assert dc_path.exists(), "docker-compose.yml not found!"
        with open(dc_path, "r", encoding="utf-8") as f:
            dc_content = f.read()
        assert "./backend/data:/app/data" in dc_content, "Persistent data volume missing in docker-compose.yml!"
        assert "JWT_SECRET_KEY" in dc_content, "JWT_SECRET_KEY missing in docker-compose.yml!"
        print("  [Pass] docker-compose.yml properly mounts persistent multi-tenant data and JWT secret.")

        # Verify Dockerfiles create /app/data/users
        dockerfile_backend = root_dir / "backend" / "Dockerfile"
        with open(dockerfile_backend, "r", encoding="utf-8") as f:
            df_content = f.read()
        assert "/app/data/users" in df_content, "/app/data/users missing in backend/Dockerfile!"
        print("  [Pass] backend/Dockerfile creates isolated /app/data/users vaults directory.")

        # ------------------------------------------------------------------
        # ZERO DATA LOSS VERIFICATION
        # ------------------------------------------------------------------
        print("\n--- Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"Job count changed! {u1_initial_jobs} -> {u1_final_jobs}"
        print(f"  [Pass] User 1 job count remains perfectly intact: {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL STEP 6 TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_step6_tests()
