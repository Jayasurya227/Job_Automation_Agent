"""
Script to capture Pipeline Page with Dynamic Multi-Portal Session Warning Banner.
"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\jaswa\.gemini\antigravity\brain\c977a61b-e7f0-4d2a-8856-8d5755cf34e1")

def capture_ui():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto("http://localhost:5173", timeout=30000)
        time.sleep(2)

        if page.query_selector("#auth-first-name"):
            page.fill("#auth-first-name", "Jayasurya")
            page.fill("#auth-last-name", "Rayavaram")
            page.fill("#auth-password", "Jayasurya@123")
            page.click("#auth-submit-btn")
            time.sleep(2)

        # On Home (Pipeline) page
        pipeline_btn = page.wait_for_selector("#tab-btn-pipeline", timeout=15000)
        if pipeline_btn:
            pipeline_btn.click()
            time.sleep(2)

        desktop_path = artifact_dir / "pipeline_dynamic_session_banner.png"
        page.screenshot(path=str(desktop_path), full_page=True)
        print(f"Saved: {desktop_path}")

        # Now click the dynamic button to verify redirect
        btn = page.wait_for_selector(".session-reconnect-btn", timeout=5000)
        if btn:
            print("Clicking dynamic banner button...")
            btn.click()
            time.sleep(2)
            redirect_path = artifact_dir / "pipeline_dynamic_redirect_verified.png"
            page.screenshot(path=str(redirect_path), full_page=True)
            print(f"Saved: {redirect_path}")

        browser.close()

if __name__ == "__main__":
    capture_ui()
