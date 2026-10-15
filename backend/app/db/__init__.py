"""
Package: app.db
Purpose: Database layer for Job Automation Agent (SQLite local / PostgreSQL cloud).
Standards: Rule 2 (Type-Safety), Rule 3 (Low Code & High Accuracy), Rule 4 (Standard Layout).
"""
from app.db.session import Base, engine, get_db, init_db
from app.db.models import Job, JobEvaluation, Application, ApplicationAnswer

__all__ = ["Base", "engine", "get_db", "init_db", "Job", "JobEvaluation", "Application", "ApplicationAnswer"]
