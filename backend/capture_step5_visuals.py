"""
Script to capture screenshots of Step 5 Indeed Dual-Mode & Mobile Auth UI.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\jaswa\.gemini\antigravity\brain\c977a61b-e7f0-4d2a-8856-8d5755cf34e1")

def capture_ui():
    with sync_playwright() as p:
        # 1. Desktop capture
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        print("Navigating to http://localhost:5173 ...")
        page.goto("http://localhost:5173", timeout=30000)
        time.sleep(2)

        if page.query_selector("#auth-first-name"):
            page.fill("#auth-first-name", "Jayasurya")
            page.fill("#auth-last-name", "Rayavaram")
            page.fill("#auth-password", "Jayasurya@123")
            page.click("#auth-submit-btn")
            time.sleep(2)

        settings_btn = page.wait_for_selector("#tab-btn-settings", timeout=15000)
        if settings_btn:
            settings_btn.click()
            time.sleep(1)

        # Click Portal Accounts sub-tab
        portal_tab = page.wait_for_selector("button:has-text('Portal Accounts')", timeout=10000)
        if portal_tab:
            portal_tab.click()
            time.sleep(2)

        desktop_path = artifact_dir / "clean_portal_accounts_desktop.png"
        page.screenshot(path=str(desktop_path), full_page=True)
        print(f"Saved: {desktop_path}")
        browser.close()

        # 2. Mobile capture
        browser_mobile = p.chromium.launch(headless=True)
        page_mobile = browser_mobile.new_page(viewport={"width": 390, "height": 844})
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

        mobile_path = artifact_dir / "clean_portal_accounts_mobile.png"
        page_mobile.screenshot(path=str(mobile_path), full_page=True)
        print(f"Saved: {mobile_path}")
        browser_mobile.close()

if __name__ == "__main__":
    capture_ui()
