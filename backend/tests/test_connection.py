"""
Module: test_connection.py
Purpose: Step 1.1 Foundation Health Check - Verifies Anthropic Claude API connectivity.
Standards: Rule 1 (Senior Scrutiny), Rule 2 (Secure Env Loading), Rule 3 (Concise & Accurate).
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import anthropic
from dotenv import load_dotenv

def test_claude_connection() -> bool:
    # 1. Load environment variables from backend/.env
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")

    # 2. Production Security Check: Validate key existence
    if not api_key or api_key == "your_anthropic_api_key_here":
        print("\n[ERROR] ANTHROPIC_API_KEY is missing or set to placeholder in backend/.env")
        print("Please paste your real API key into backend/.env (ANTHROPIC_API_KEY=sk-ant-...)")
        return False

    print(f"\n[INFO] Initializing Claude client ({model})...")
    try:
        client = anthropic.Anthropic(api_key=api_key)

        print("[INFO] Sending connectivity ping to Anthropic...")
        response = client.messages.create(
            model=model,
            max_tokens=50,
            messages=[{"role": "user", "content": "Respond with exactly: 'AI Brain Connected Successfully.'"}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()

        # 3. Output Verification
        print("\n" + "=" * 55)
        print("  CLAUDE API HEALTH CHECK: PASSED")
        print(f"  AI Response: {text}")
        print("=" * 55 + "\n")
        assert text != ""
        return True

    except Exception as e:
        print("\n" + "!" * 55)
        print("  CLAUDE API HEALTH CHECK: FAILED")
        print(f"  Details: {str(e)}")
        print("!" * 55 + "\n")
        assert False, f"Claude API health check failed: {e}"

if __name__ == "__main__":
    success = test_claude_connection()
    sys.exit(0 if success else 1)
