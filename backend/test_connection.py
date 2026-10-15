"""
Module: test_connection.py
Purpose: Step 1.1 Foundation Health Check - Verifies Google Gemini API connectivity.
Standards: Rule 1 (Senior Scrutiny), Rule 2 (Secure Env Loading), Rule 3 (Concise & Accurate).
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
import google.generativeai as genai

def test_gemini_connection() -> bool:
    # 1. Load environment variables from backend/.env
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    # 2. Production Security Check: Validate key existence
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n[ERROR] GEMINI_API_KEY is missing or set to placeholder in backend/.env")
        print("Please paste your real API key into backend/.env (GEMINI_API_KEY=AIzaSy...)")
        return False

    print("\n[INFO] Initializing Gemini Flash Client...")
    try:
        # 3. Configure Gemini SDK
        genai.configure(api_key=api_key)
        
        # 4. Use verified production model: gemini-2.5-flash
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        print("[INFO] Sending connectivity ping to Google Gemini...")
        response = model.generate_content("Respond with exactly: 'AI Brain Connected Successfully.'")
        
        # 5. Output Verification
        print("\n" + "=" * 55)
        print("  GEMINI API HEALTH CHECK: PASSED")
        print(f"  AI Response: {response.text.strip()}")
        print("=" * 55 + "\n")
        assert response.text.strip() != ""

    except Exception as e:
        print("\n" + "!" * 55)
        print("  GEMINI API HEALTH CHECK: FAILED")
        print(f"  Details: {str(e)}")
        print("!" * 55 + "\n")
        assert False, f"Gemini API health check failed: {e}"

if __name__ == "__main__":
    success = test_gemini_connection()
    sys.exit(0 if success else 1)
