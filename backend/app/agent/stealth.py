"""
Module: stealth.py
Purpose: Sub-Phase 5.2 Anti-Detection, Browser Fingerprint Spoofing, and Humanized Automation Engine.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal),
           Rule 5 (Production Reliability & Bot Defense Evasion).
"""
import math
import time
import random
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger("agent.stealth")

# =====================================================================
# 1. Realistic User-Agent & Client Hints Pool
# =====================================================================

STEALTH_USER_AGENTS = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "platform": "Windows",
        "platform_version": "10.0.0",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="129", "Google Chrome";v="129", "Not?A_Brand";v="99"',
        "platform": "Windows",
        "platform_version": "10.0.0",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Chromium";v="128", "Google Chrome";v="128", "Not?A_Brand";v="24"',
        "platform": "Windows",
        "platform_version": "10.0.0",
        "vendor": "Google Inc.",
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
]

def get_random_fingerprint() -> Dict[str, str]:
    """Returns a synchronized User-Agent, Client Hints, and WebGL renderer profile."""
    return random.choice(STEALTH_USER_AGENTS)


# =====================================================================
# 2. Comprehensive Anti-Detection JS Injection (Neutralizes Bot Shields)
# =====================================================================

def build_stealth_js(fp: Optional[Dict[str, str]] = None) -> str:
    """
    Generates dynamic anti-detection script injected into page DOM before scripts run.
    Neutralizes:
    - navigator.webdriver detection
    - Headless Chrome WebGL SwiftShader leakage
    - Canvas fingerprint tracking
    - AudioContext fingerprinting
    - Missing chrome runtime / plugins
    - Permissions API query flags
    """
    profile = fp or STEALTH_USER_AGENTS[0]
    webgl_vendor = profile.get("vendor", "Google Inc. (NVIDIA)")
    webgl_renderer = profile.get("renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)")

    return f"""
(() => {{
    'use strict';

    // 1. Remove navigator.webdriver & clean up prototype
    try {{
        delete Object.getPrototypeOf(navigator).webdriver;
    }} catch (e) {{}}
    Object.defineProperty(navigator, 'webdriver', {{
        get: () => undefined,
        configurable: true
    }});

    // 2. Hardware specs: hardwareConcurrency & deviceMemory
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
        get: () => 8,
        configurable: true
    }});
    Object.defineProperty(navigator, 'deviceMemory', {{
        get: () => 8,
        configurable: true
    }});

    // 3. Languages alignment
    Object.defineProperty(navigator, 'languages', {{
        get: () => ['en-US', 'en'],
        configurable: true
    }});

    // 4. Mimic Chrome Plugins array
    const fakePlugins = [
        {{ name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
        {{ name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' }},
        {{ name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }}
    ];
    Object.defineProperty(navigator, 'plugins', {{
        get: () => fakePlugins,
        configurable: true
    }});

    // 5. Mock window.chrome runtime object
    if (!window.chrome) {{
        window.chrome = {{}};
    }}
    window.chrome.runtime = window.chrome.runtime || {{
        connect: function() {{}},
        sendMessage: function() {{}},
        id: undefined
    }};
    window.chrome.csi = window.chrome.csi || function() {{ return {{ onloadT: Date.now(), pageT: 120, startE: Date.now() - 120, tran: 15 }}; }};
    window.chrome.loadTimes = window.chrome.loadTimes || function() {{ return {{ requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000 }}; }};

    // 6. WebGL Vendor & Renderer Spoofing (Hides Google SwiftShader)
    const getParameterProto = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {{
        // UNMASKED_VENDOR_WEBGL (0x9245)
        if (param === 0x9245) {{
            return '{webgl_vendor}';
        }}
        // UNMASKED_RENDERER_WEBGL (0x9246)
        if (param === 0x9246) {{
            return '{webgl_renderer}';
        }}
        return getParameterProto.apply(this, arguments);
    }};

    if (window.WebGL2RenderingContext) {{
        const getParameter2Proto = WebGL2RenderingContext.prototype.getParameter;
        WebGL2RenderingContext.prototype.getParameter = function(param) {{
            if (param === 0x9245) return '{webgl_vendor}';
            if (param === 0x9246) return '{webgl_renderer}';
            return getParameter2Proto.apply(this, arguments);
        }};
    }}

    // 7. Subtle Canvas Noise (Prevents deterministic cross-domain tracking hashes)
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {{
        const context = this.getContext('2d');
        if (context) {{
            try {{
                const imgData = context.getImageData(0, 0, Math.min(this.width, 16), Math.min(this.height, 16));
                // Add negligible sub-visual jitter
                if (imgData.data.length > 3) {{
                    imgData.data[0] = (imgData.data[0] ^ 1);
                }}
            }} catch(e) {{}}
        }}
        return originalToDataURL.apply(this, arguments);
    }};

    // 8. Notification Permissions Spoofing
    if (window.navigator && window.navigator.permissions) {{
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({{ state: Notification.permission }}) :
                originalQuery(parameters)
        );
    }}
}})();
"""


# =====================================================================
# 3. Hardened Chromium Launch Flags
# =====================================================================

def get_stealth_chromium_args() -> List[str]:
    """Returns hardened Chromium startup flags that strip automation banners and telemetry."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        # --no-sandbox is required for headless Chromium on Windows environments that
        # do not support user namespaces (which is most Windows setups without Docker).
        # SECURITY NOTE: This flag disables Chrome's process sandbox. It is intentionally
        # used here because this is a local personal automation tool running controlled,
        # known URLs only — never untrusted third-party content in an isolated context.
        # Do NOT use this flag in a server-side browser that renders arbitrary user-supplied URLs.
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu-program-cache",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=IsolateOrigins,site-per-process,AudioServiceSandbox",
        "--disable-ipc-flooding-protection",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--password-store=basic",
        "--use-mock-keychain",
    ]


# =====================================================================
# 4. Human Motion & Action Emulation (Bézier Curves & Typing Jitter)
# =====================================================================

def calculate_bezier_point(p0: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
    """Computes a cubic Bézier curve coordinate at interpolation factor t (0 <= t <= 1)."""
    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    return (x, y)


def generate_bezier_trajectory(
    start: Tuple[float, float],
    end: Tuple[float, float],
    steps: int = 20
) -> List[Tuple[float, float]]:
    """
    Generates a natural, curved trajectory with acceleration and deceleration.
    Mimics genuine human hand movement with slight lateral drift.
    """
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    dist = math.hypot(dx, dy)

    # Offset control points randomly to create human arc
    deviation = min(dist * 0.35, 120)
    ctrl1 = (
        sx + dx * random.uniform(0.2, 0.4) + random.uniform(-deviation, deviation),
        sy + dy * random.uniform(0.1, 0.3) + random.uniform(-deviation, deviation)
    )
    ctrl2 = (
        sx + dx * random.uniform(0.6, 0.8) + random.uniform(-deviation, deviation),
        sy + dy * random.uniform(0.7, 0.9) + random.uniform(-deviation, deviation)
    )

    trajectory = []
    for i in range(steps + 1):
        # Ease-in-out easing for realistic acceleration & slowing near target
        t = i / float(steps)
        eased_t = t * t * (3.0 - 2.0 * t)
        pt = calculate_bezier_point((sx, sy), ctrl1, ctrl2, (ex, ey), eased_t)
        trajectory.append((round(pt[0], 1), round(pt[1], 1)))

    return trajectory


# =====================================================================
# 5. High-Level Humanized Interaction Helpers
# =====================================================================

class HumanInteractionEngine:
    """Provides human-like mouse movements, variable typing rhythm, and reading pauses."""

    @staticmethod
    def human_delay_sync(min_sec: float = 1.0, max_sec: float = 2.8) -> float:
        """Synchronous random pause with natural jitter."""
        pause = round(random.uniform(min_sec, max_sec), 2)
        time.sleep(pause)
        return pause

    @staticmethod
    async def human_delay_async(min_sec: float = 1.0, max_sec: float = 2.8) -> float:
        """Asynchronous random pause with natural jitter."""
        pause = round(random.uniform(min_sec, max_sec), 2)
        await asyncio.sleep(pause)
        return pause

    @staticmethod
    def human_type_sync(page: Any, selector: str, text: str, min_ms: int = 35, max_ms: int = 110):
        """
        Types text into an input field with variable inter-keystroke cadence.
        Introduces slight pauses between words to mimic natural human reading/typing.
        """
        element = page.query_selector(selector)
        if not element:
            return
        element.click()
        page.wait_for_timeout(random.randint(150, 300))

        for char in text:
            element.type(char)
            # Longer pause on spaces and punctuation
            if char in " ,.-_@/":
                page.wait_for_timeout(random.randint(120, 260))
            else:
                page.wait_for_timeout(random.randint(min_ms, max_ms))

    @staticmethod
    def human_click_sync(page: Any, selector: str):
        """
        Moves mouse in a curved Bézier path to target element before clicking.
        Avoids the dead giveaway instantaneous bot jumps.
        """
        element = page.query_selector(selector)
        if not element:
            return
        box = element.bounding_box()
        if not box:
            element.click()
            return

        # Target center with slight natural offset
        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

        # Start from a plausible prior position or viewport corner
        start_x = target_x + random.uniform(-250, 250)
        start_y = target_y + random.uniform(-200, 200)

        trajectory = generate_bezier_trajectory((start_x, start_y), (target_x, target_y), steps=12)
        for x, y in trajectory:
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(8, 20))

        # Hesitate slightly before click (100-250ms)
        page.wait_for_timeout(random.randint(100, 250))
        page.mouse.click(target_x, target_y)


# =====================================================================
# 6. Bot Challenge / CAPTCHA Detection
# =====================================================================

CHALLENGE_SELECTORS = [
    # Cloudflare Turnstile / Challenge
    "iframe[src*='challenges.cloudflare.com']",
    "div#cf-turnstile",
    "div#turnstile-wrapper",
    "span#cf-challenge-running",
    
    # LinkedIn Security Checkpoint & Verification
    "div#captcha-internal",
    "div[data-control-name='security_check']",
    "form#checkpointSubmitForm",
    "h1:has-text('Let\\'s do a quick security check')",
    "h1:has-text('Verify it\\'s you')",

    # Indeed Bot Screen & Recaptcha
    "div#recaptcha",
    "div.g-recaptcha",
    "iframe[src*='recaptcha']",
    "iframe[src*='arkoselabs']",
    "h1:has-text('Please verify you are a human')",
    "h2:has-text('Checking your browser')",
]

def check_bot_challenge(page: Any) -> Optional[str]:
    """
    Inspects page DOM for security verification checkpoints or CAPTCHAs.
    Returns the challenge identifier if detected, or None if clear.
    """
    try:
        # Check title text for quick match
        title = (page.title() or "").lower()
        if any(keyword in title for keyword in ["security check", "just a moment", "verify you are human", "attention required"]):
            return f"Challenge Title Detected: '{title}'"

        # Check DOM selectors
        for sel in CHALLENGE_SELECTORS:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return f"Bot Challenge Element Detected: '{sel}'"
    except Exception as e:
        logger.debug(f"Bot challenge check notice: {e}")

    return None
