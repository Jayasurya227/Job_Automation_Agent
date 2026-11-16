"""
Module: user_cleanup.py
Purpose: Enterprise-Grade Safe Multi-Tenant Cleanup & Purge Engine (Phase 5 Step 1).
Provides surgical cleanup of testing/transient tenants while protecting Master User 1.
"""
import shutil
import logging
from pathlib import Path
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.db.models import User, Job, Application, ApplicationAnswer
from app.core.user_storage import get_user_base_dir

logger = logging.getLogger("user_cleanup")


def purge_tenant_data(user_id: int, db: Session, allow_master_purge: bool = False) -> Dict[str, Any]:
    """
    Surgically purges all database records and filesystem vaults for a specified tenant.
    
    SAFETY RULE: User ID 1 (Master User - Rayavaram Jayasurya) is permanently protected 
    against accidental deletion unless allow_master_purge is explicitly True.
    """
    if user_id == 1 and not allow_master_purge:
        raise PermissionError("Master Tenant Guard: User 1 (Rayavaram Jayasurya) cannot be deleted.")

    stats: Dict[str, Any] = {
        "user_id": user_id,
        "jobs_deleted": 0,
        "applications_deleted": 0,
        "qa_items_deleted": 0,
        "user_deleted": False,
        "vault_directory_removed": False,
    }

    try:
        # 1. Clean child records in database
        app_count = db.query(Application).filter(Application.user_id == user_id).delete(synchronize_session=False)
        job_count = db.query(Job).filter(Job.user_id == user_id).delete(synchronize_session=False)
        qa_count = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == user_id).delete(synchronize_session=False)
        user_deleted = db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        
        db.commit()

        stats["applications_deleted"] = app_count
        stats["jobs_deleted"] = job_count
        stats["qa_items_deleted"] = qa_count
        stats["user_deleted"] = bool(user_deleted)

        # 2. Clean isolated filesystem vault
        vault_dir = get_user_base_dir(user_id)
        if vault_dir.exists():
            shutil.rmtree(vault_dir)
            stats["vault_directory_removed"] = True

        logger.info(f"Successfully purged tenant {user_id}: {stats}")
        return stats

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to purge tenant {user_id}: {e}")
        raise
