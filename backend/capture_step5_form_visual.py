"""
Script to capture Indeed Mobile Reconnect Form screenshot.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\jaswa\.gemini\antigravity\brain\c977a61b-e7f0-4d2a-8856-8d5755cf34e1")

def capture_ui():
    with sync_playwright() as p:
        browser_mobile = p.chromium.launch(headless=True)
        page_mobile = browser_mobile.new_page(viewport={"width": 390, "height": 950})
        page_mobile.goto("http://localhost:5173", timeout=30000)
        time.sleep(2)

        if page_mobile.query_selector("#auth-first-name"):
            page_mobile.fill("#auth-first-name", "Jayasurya")
            page_mobile.fill("#auth-last-name", "Rayavaram")
            page_mobile.fill("#auth-password", "Jayasurya@123")
            page_mobile.click("#auth-submit-btn")
            time.sleep(2)

        settings_btn_m = page_mobile.wait_for_selector("#tab-btn-settings", timeout=15000)
        if settings_btn_m:
            settings_btn_m.click()
            time.sleep(1)

        portal_tab_m = page_mobile.wait_for_selector("button:has-text('Portal Accounts')", timeout=10000)
        if portal_tab_m:
            portal_tab_m.click()
            time.sleep(2)

        # Click Naukri Re-connect button to show the mobile form
        reconnect_btn = page_mobile.wait_for_selector("button:has-text('Re-connect / Refresh Mobile Session')", timeout=10000)
        if reconnect_btn:
            reconnect_btn.click()
            time.sleep(1)

        mobile_path = artifact_dir / "naukri_clean_mobile_form.png"
        page_mobile.screenshot(path=str(mobile_path), full_page=True)
        print(f"Saved: {mobile_path}")
        browser_mobile.close()

if __name__ == "__main__":
    capture_ui()

