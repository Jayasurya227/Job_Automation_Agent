"""
Module: test_step2_api.py
Purpose: Rigorous automated verification for Step 2 FastAPI Mobile Connection Endpoints.
"""
import sys
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_endpoints():
    print("🔍 Testing FastAPI routes registration for Step 2 Mobile Auth...")
    
    routes = [r.path for r in app.routes]
    assert "/api/portals/naukri/connect-mobile" in routes, "connect-mobile route missing"
    assert "/api/portals/naukri/verify-otp" in routes, "verify-otp route missing"
    assert "/api/portals/naukri/cancel-mobile" in routes, "cancel-mobile route missing"
    print(" All 3 new mobile connection routes are registered in FastAPI!")

    print("\n🔍 Testing Pydantic validation on connect-mobile (Empty payload)...")
    res = client.post("/api/portals/naukri/connect-mobile", json={})
    assert res.status_code == 422, f"Expected 422 for missing identifier, got {res.status_code}"
    print(" 422 Unprocessable Entity returned correctly for missing fields!")

    print("\n🔍 Testing Pydantic validation on verify-otp (Invalid OTP length)...")
    res = client.post("/api/portals/naukri/verify-otp", json={"session_id": "test-uuid", "otp": "12"})
    assert res.status_code == 422, f"Expected 422 for short OTP, got {res.status_code}"
    print(" 422 Unprocessable Entity returned correctly for invalid OTP length!")

    print("\n🔍 Testing verify-otp with expired / non-existent session_id...")
    res = client.post("/api/portals/naukri/verify-otp", json={"session_id": "00000000-0000-0000-0000-000000000000", "otp": "123456"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ERROR"
    assert "expired or not found" in data["message"].lower()
    print(f" Correct structured response received: {data}")

    print("\n🔍 Testing cancel-mobile endpoint...")
    res = client.post("/api/portals/naukri/cancel-mobile", json={"session_id": "test-session-id"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "cancelled"
    print(f" Correct cancel response received: {data}")

    print("\n🎉 Step 2 API verification completed with 100% success!")

if __name__ == "__main__":
    test_endpoints()

