"""
Browser Automation & Session Management Module.
Implements persistent Chromium contexts with anti-bot stealth parameters and human-like interaction pacing.
Part of Phase 3: Browser Automation & Job Discovery.
"""

import asyncio
import random
import logging
from pathlib import Path
from typing import Optional, AsyncGenerator, Any, cast
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger("agent.browser")

try:
    from app.agent.stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        generate_bezier_trajectory,
        check_bot_challenge,
    )
except ImportError:
    from .stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        generate_bezier_trajectory,
        check_bot_challenge,
    )

# Path to persistent browser user data directory (gitignored)
DEFAULT_SESSION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "browser_session"

# Standard realistic Windows Chrome User-Agent
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Active dynamic anti-detection script
STEALTH_INIT_SCRIPT = build_stealth_js()


class BrowserSessionManager:
    """
    Manages persistent Chromium browser contexts with stealth configurations
    and human-like pacing for job discovery and portal interaction.
    """

    def __init__(
        self,
        session_dir: Optional[Path] = None,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 800,
        user_agent: Optional[str] = None,
    ):
        self.session_dir = Path(session_dir or DEFAULT_SESSION_DIR)
        self.headless = headless
        self.viewport = {"width": viewport_width, "height": viewport_height}
        self.user_agent = user_agent or get_random_fingerprint()["user_agent"]
        self._ensure_session_dir()

    def _ensure_session_dir(self) -> None:
        """Creates the session directory if it does not already exist."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_launch_args(self) -> list[str]:
        """Returns hardened Chromium launch flags to bypass bot detection."""
        return get_stealth_chromium_args()

    @asynccontextmanager
    async def get_context(self, headless: Optional[bool] = None) -> AsyncGenerator[BrowserContext, None]:
        """
        Async context manager providing a persistent Playwright browser context.
        Saves all cookies, local storage, and session tokens across runs.
        """
        is_headless = self.headless if headless is None else headless

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                headless=is_headless,
                viewport=cast(Any, self.viewport),
                user_agent=self.user_agent,
                args=self.get_launch_args(),
                locale="en-US",
                timezone_id="Asia/Kolkata",
                ignore_https_errors=True,
            )

            # Inject anti-detection stealth script into all existing & future pages
            await context.add_init_script(build_stealth_js())

            try:
                yield context
            finally:
                try:
                    await context.close()
                except Exception as e:
                    logger.debug(f"Context closed with notice: {e}")

    @asynccontextmanager
    async def get_page(self, headless: Optional[bool] = None) -> AsyncGenerator[Page, None]:
        """
        Convenience context manager yielding an active, stealth-injected Page.
        """
        async with self.get_context(headless=headless) as context:
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            yield page

    @staticmethod
    async def random_delay(min_sec: float = 2.5, max_sec: float = 6.5) -> float:
        """
        Sleeps for a randomized duration to mimic human pauses and avoid bot triggers.
        Returns the actual duration slept.
        """
        duration = round(random.uniform(min_sec, max_sec), 2)
        await asyncio.sleep(duration)
        return duration

    @staticmethod
    async def human_scroll(page: Page, scrolls: int = 3, min_delay: float = 1.0, max_delay: float = 2.5) -> None:
        """
        Smoothly scrolls down the page in randomized increments to simulate human browsing.
        """
        for _ in range(scrolls):
            delta_y = random.randint(300, 700)
            await page.mouse.wheel(0, delta_y)
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    @staticmethod
    async def human_type(page: Page, selector: str, text: str, min_delay_ms: int = 35, max_delay_ms: int = 110) -> None:
        """
        Types text character-by-character into an input field with natural typing cadence
        and slight micro-pauses at punctuation/spaces.
        """
        await page.click(selector)
        await asyncio.sleep(random.uniform(0.1, 0.25))
        for char in text:
            await page.keyboard.type(char)
            if char in " ,.-_@/":
                await asyncio.sleep(random.uniform(0.12, 0.26))
            else:
                await asyncio.sleep(random.uniform(min_delay_ms, max_delay_ms) / 1000.0)

    @staticmethod
    async def human_click(page: Page, selector: str) -> None:
        """
        Moves mouse along a curved Bézier path to target element before clicking.
        Prevents detection by behavioral biometrics analysis.
        """
        element = await page.query_selector(selector)
        if not element:
            return
        box = await element.bounding_box()
        if not box:
            await element.click()
            return

        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        start_x = target_x + random.uniform(-200, 200)
        start_y = target_y + random.uniform(-150, 150)

        trajectory = generate_bezier_trajectory((start_x, start_y), (target_x, target_y), steps=12)
        for x, y in trajectory:
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.008, 0.020))

        await asyncio.sleep(random.uniform(0.1, 0.25))
        await page.mouse.click(target_x, target_y)

    @staticmethod
    def check_challenge(page: Any) -> Optional[str]:
        """Inspects page for Cloudflare Turnstile, LinkedIn security checkpoint, or CAPTCHA."""
        return check_bot_challenge(page)

    @staticmethod
    async def safe_goto(page: Page, url: str, wait_until: Any = "domcontentloaded", timeout: int = 30000) -> bool:
        """
        Navigates to a URL safely with error handling and timeout protection.
        Returns True on success, False on network/timeout failure.
        """
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Failed to navigate to {url}: {e}")
            return False


# Global default instance
browser_manager = BrowserSessionManager()
