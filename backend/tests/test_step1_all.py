"""
Master Test Runner: Step 1 (Security & Identity Layer) - All 8 Issues
Validates complete multi-tenant hardening and isolation for Step 1.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from test_step1_issue1 import test_issue_1_1
from test_step1_issue2 import test_issue_1_2
from test_step1_issue3 import test_issue_1_3
from test_step1_issues4_5 import test_issues_1_4_and_1_5
from test_step1_issue6 import test_issue_1_6
from test_step1_issue7 import test_issue_1_7
from test_step1_issue8 import test_issue_1_8

async def main():
    print("\n" + "#" * 70)
    print("  🚀 STEP 1 FULL REGRESSION & COMPLIANCE SUITE (ISSUES 1.1 -> 1.8)")
    print("#" * 70 + "\n")

    # Issue 1.1: Strict Token Enforcement & Zero User 1 Fallback
    test_issue_1_1()

    # Issue 1.2: Naukri Mobile OTP Scoping & Anti-Hijacking
    await test_issue_1_2()

    # Issue 1.3: Indeed Session Vault Isolation & Anti-Hijacking
    await test_issue_1_3()

    # Issues 1.4 & 1.5: Workflow Apply & Resume Endpoints Auth & User Scoping
    await test_issues_1_4_and_1_5()

    # Issue 1.6: Master Resume & Profile Lookups & Downloads User Isolation
    await test_issue_1_6()

    # Issue 1.7: Settings Endpoint Per-User Isolation (account_settings.json)
    test_issue_1_7()

    # Issue 1.8: Output Snapshots Route Protection & User Isolation
    test_issue_1_8()

    print("\n" + "#" * 70)
    print("  🎉 STEP 1 100% COMPLETE & VERIFIED: ALL 8 ISSUES SECURED!")
    print("#" * 70 + "\n")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
