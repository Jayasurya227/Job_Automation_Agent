"""
Module: test_profile.py
Purpose: Step 1.2 Verification - Validates profile.json against CandidateProfile Pydantic schema.
Standards: Rule 1 (Senior Validation), Rule 2 (Type Integrity), Rule 3 (Low Code & High Accuracy).
"""
import json
import sys
from pathlib import Path
from pydantic import ValidationError

from app.schemas.profile import CandidateProfile

def validate_profile(profile_path: str = "profile.json") -> bool:
    target = Path(profile_path)
    if not target.exists():
        print(f"\n[ERROR] File not found: {profile_path}")
        return False

    try:
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Enforce strict Pydantic validation (Rule 2)
        profile = CandidateProfile(**data)

        # Print structured summary (Rule 1)
        print("\n" + "=" * 60)
        print("  CANDIDATE MASTER PROFILE: VALIDATED SUCCESSFULLY")
        print("=" * 60)
        print(f"  Candidate Name   : {profile.personal_info.name}")
        print(f"  Target Roles     : {', '.join(profile.preferences.target_roles)}")
        print(f"  Core Languages   : {', '.join(profile.technical_skills.programming_languages)}")
        print(f"  AI & ML Skills   : {', '.join(profile.technical_skills.ai_and_ml)}")
        print(f"  Work Experience  : {len(profile.experience)} role(s) documented")
        print(f"  Key Projects     : {len(profile.projects)} production/R&D projects")
        print(f"  Notice Period    : {profile.preferences.notice_period_days} days (Immediate)")
        print("=" * 60 + "\n")
        return True

    except json.JSONDecodeError as jde:
        print(f"\n[ERROR] Invalid JSON syntax in {profile_path}: {jde}")
        return False
    except ValidationError as ve:
        print(f"\n[ERROR] Schema Validation Failed:\n{ve}")
        return False

if __name__ == "__main__":
    is_valid = validate_profile()
    sys.exit(0 if is_valid else 1)
