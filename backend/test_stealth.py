"""
Test Suite: test_stealth.py
Validates Sub-Phase 5.2 Anti-Detection, Fingerprint Spoofing, Bézier Motion & Bot Defense Evasion.
"""
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

from app.agent.stealth import (
    build_stealth_js,
    get_stealth_chromium_args,
    get_random_fingerprint,
    generate_bezier_trajectory,
    calculate_bezier_point,
    check_bot_challenge,
    HumanInteractionEngine,
    STEALTH_USER_AGENTS,
)
from app.agent.applier import EasyApplyFiller, FormFillResult


def test_stealth_js_and_chromium_args_generation():
    """Verify stealth script and Chromium args contain required anti-bot signatures."""
    fp = get_random_fingerprint()
    assert "user_agent" in fp
    assert "vendor" in fp
    assert "renderer" in fp

    js = build_stealth_js(fp)
    assert "navigator.webdriver" in js
    assert "hardwareConcurrency" in js
    assert "deviceMemory" in js
    assert "fakePlugins" in js
    assert "window.chrome.runtime" in js
    assert "0x9245" in js  # UNMASKED_VENDOR_WEBGL
    assert "0x9246" in js  # UNMASKED_RENDERER_WEBGL
    assert fp["vendor"] in js
    assert fp["renderer"] in js
    assert "originalToDataURL" in js

    args = get_stealth_chromium_args()
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--no-sandbox" in args
    assert "--disable-infobars" in args
    assert any("IsolateOrigins" in a for a in args)


def test_bezier_trajectory_math():
    """Verify cubic Bézier curve calculation and acceleration trajectory."""
    start = (100.0, 100.0)
    end = (500.0, 400.0)
    steps = 15

    points = generate_bezier_trajectory(start, end, steps=steps)
    assert len(points) == steps + 1
    assert points[0] == start
    assert points[-1] == end

    # Test midpoint calculation
    mid = calculate_bezier_point(
        (0.0, 0.0), (10.0, 20.0), (30.0, 40.0), (50.0, 50.0), 0.5
    )
    assert isinstance(mid, tuple)
    assert len(mid) == 2
    assert mid[0] > 0 and mid[1] > 0


def test_bot_challenge_detection():
    """Verify detection logic accurately catches bot verification pages and ignores normal pages."""
    class MockElement:
        def __init__(self, visible=True):
            self._visible = visible
        def is_visible(self):
            return self._visible

    class MockPageChallenge:
        def title(self):
            return "Attention Required! | Cloudflare"
        def query_selector(self, sel):
            return None

    class MockPageNormal:
        def title(self):
            return "Senior AI Engineer Application - NextGen AI"
        def query_selector(self, sel):
            return None

    class MockPageDOMChallenge:
        def title(self):
            return "Job Application Form"
        def query_selector(self, sel):
            if "cf-turnstile" in sel or "captcha" in sel:
                return MockElement(visible=True)
            return None

    # Title match
    res1 = check_bot_challenge(MockPageChallenge())
    assert res1 is not None
    assert "Challenge Title" in res1

    # Normal page
    res2 = check_bot_challenge(MockPageNormal())
    assert res2 is None

    # DOM element challenge
    res3 = check_bot_challenge(MockPageDOMChallenge())
    assert res3 is not None
    assert "Bot Challenge Element" in res3


def test_browser_stealth_dom_injection():
    """Verify in real Chromium that stealth script successfully spoofes browser properties."""
    fp = STEALTH_USER_AGENTS[0]
    args = get_stealth_chromium_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=args)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=fp["user_agent"],
        )
        context.add_init_script(build_stealth_js(fp))
        page = context.new_page()

        # Load blank or data page to execute init script
        page.goto("data:text/html,<html><body><h1>Stealth Test</h1></body></html>")

        # 1. navigator.webdriver must be undefined
        webdriver_flag = page.evaluate("() => navigator.webdriver")
        assert webdriver_flag is None or webdriver_flag is False

        # 2. Hardware specs spoofed
        concurrency = page.evaluate("() => navigator.hardwareConcurrency")
        assert concurrency == 8

        mem = page.evaluate("() => navigator.deviceMemory")
        assert mem == 8

        # 3. Plugins array populated
        plugins_count = page.evaluate("() => navigator.plugins.length")
        assert plugins_count >= 3

        # 4. Chrome runtime mocked
        has_runtime = page.evaluate("() => Boolean(window.chrome && window.chrome.runtime)")
        assert has_runtime is True

        # 5. WebGL vendor spoofed
        webgl_info = page.evaluate("""() => {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return { vendor: null, renderer: null };
            const ext = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                vendor: ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : null,
                renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null
            };
        }""")

        assert webgl_info["vendor"] == fp["vendor"]
        assert webgl_info["renderer"] == fp["renderer"]
        assert "SwiftShader" not in (webgl_info["renderer"] or "")

        browser.close()


def test_human_interaction_and_staging():
    """Verify EasyApplyFiller operates with stealth scripts and human interactions."""
    mock_file = Path("data/mock_easy_apply.html").resolve()
    filler = EasyApplyFiller(headless=True)

    result = filler.fill_and_stage_application(
        target_url_or_path=str(mock_file),
        job_title="Lead AI Engineer",
        company_name="DeepInnovate Labs",
        thread_id="test_stealth_staging",
        auto_submit=False
    )

    assert isinstance(result, FormFillResult)
    assert result.status == "READY_FOR_REVIEW"
    assert result.steps_traversed >= 1
    assert result.snapshot_path is not None
    assert Path(result.snapshot_path).exists()
    assert len(result.filled_fields) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
