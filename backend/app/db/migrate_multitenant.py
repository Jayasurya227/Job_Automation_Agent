"""
Module: migrate_multitenant.py
Purpose: Safe, idempotent database schema migration adding Users, PasswordResetOTP,
         and user_id foreign keys to jobs, applications, and application_answers.
Standards: Rule 1 (Zero Data Loss), Rule 2 (Idempotent Execution), Rule 5 (ACID Safe).
"""
import sqlite3
import logging
from pathlib import Path
from app.db.session import engine, Base, _DATA_DIR
import app.db.models  # Ensure all declarative models are registered

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db.migrate")

def run_migration():
    logger.info("Step 1/3: Creating new tables (users, password_reset_otps)...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created or verified.")

    db_path = _DATA_DIR / "jobs.db"
    logger.info(f"Step 2/3: Checking existing table schemas in {db_path}...")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Helper function to add column if it doesn't exist
    def add_column_if_missing(table_name: str, column_name: str, col_type_sql: str):
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cur.fetchall()]
        if column_name not in columns:
            logger.info(f"Adding '{column_name}' column to '{table_name}' table...")
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_type_sql}")
            # Create index for query optimization
            idx_name = f"ix_{table_name}_{column_name}"
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({column_name})")
            logger.info(f"Added '{column_name}' and created index '{idx_name}'.")
        else:
            logger.info(f"Column '{column_name}' already exists in '{table_name}'. Skipping.")

    # 1. Add user_id to jobs
    add_column_if_missing("jobs", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")

    # 2. Add user_id to applications
    add_column_if_missing("applications", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")

    # 3. Add user_id to application_answers
    add_column_if_missing("application_answers", "user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE")

    conn.commit()
    conn.close()

    logger.info("Step 3/3: Migration successfully applied and verified.")

if __name__ == "__main__":
    run_migration()
