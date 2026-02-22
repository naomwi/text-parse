"""Browser connection, scrolling, and navigation utilities."""

import asyncio
import logging
import os
import random
import re
import shutil
import subprocess
import time
import urllib.request
import psutil

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import (
    CDP_ENDPOINT,
    CHROME_EXE,
    CHROME_USER_DATA_DIR,
    CHROME_PROFILE,
    TEMP_PROFILE_DIR,
    LOADING_TIMEOUT_MS,
    MIN_NAV_DELAY,
    MAX_NAV_DELAY,
    NOVELPIA_MAIN_URL_PATTERN,
    PIXIV_NOVEL_URL_PATTERN,
    PIXIV_SERIES_URL_PATTERN,
    SCROLL_DELAY_MS,
    SCROLL_STEP_PX,
    SEL_LOADING_VIEW,
    SEL_VIEWER_CONTENTS,
    SEL_MAIN_NOVEL_DRAWING,
)

logger = logging.getLogger(__name__)

# Playwright instance — managed by caller via start/stop
_playwright = None


async def start_playwright():
    """Start the global Playwright instance."""
    global _playwright
    _playwright = await async_playwright().start()
    return _playwright


async def stop_playwright():
    """Stop the global Playwright instance."""
    global _playwright
    if _playwright:
        await _playwright.stop()
        _playwright = None


def _is_cdp_ready(endpoint: str = CDP_ENDPOINT) -> bool:
    """Check if the CDP endpoint is responding."""
    try:
        url = endpoint.rstrip("/") + "/json/version"
        req = urllib.request.urlopen(url, timeout=2)
        req.close()
        return True
    except Exception:
        return False


def kill_chrome() -> None:
    """Force-kill all Chrome processes using psutil."""
    logger.info("Killing all Chrome processes...")
    
    procs = []
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == "chrome.exe":
                proc.kill()
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if procs:
        gone, alive = psutil.wait_procs(procs, timeout=5)
        if alive:
            logger.warning(f"Could not kill {len(alive)} Chrome processes: {alive}")
        else:
            logger.info(f"Successfully killed {len(gone)} Chrome processes.")
    else:
        logger.info("No Chrome processes found.")
    
    # Extra safety buffer
    time.sleep(1)


def setup_temp_profile() -> str:
    """Prepare a temporary profile directory. 
    
    Does NOT copy data from the real profile to avoid corruption/crashes.
    Relies on the user logging in manually once, which will persist in this directory.
    """
    kill_chrome()
    
    logger.info(f"Using persistent temporary profile at: {TEMP_PROFILE_DIR}")
    
    if not os.path.exists(TEMP_PROFILE_DIR):
        try:
            os.makedirs(TEMP_PROFILE_DIR, exist_ok=True)
            logger.info("Created new temporary profile directory.")
        except Exception as e:
            logger.error(f"Error creating temp profile: {e}")
            raise
    else:
        logger.info("Resuming session from existing temporary profile.")

    return str(TEMP_PROFILE_DIR)


def _launch_chrome_with_debugging(
    chrome_exe: str = CHROME_EXE,
    user_data_dir: str = CHROME_USER_DATA_DIR,
    profile_directory: str = CHROME_PROFILE,
    port: int = 9222,
) -> subprocess.Popen:
    """Launch Chrome with remote debugging enabled.

    Returns the Popen handle (Chrome runs as a separate process).
    """
    # Verify profile directory exists
    profile_path = os.path.join(user_data_dir, profile_directory)
    if not os.path.exists(profile_path):
        logger.warning(f"Profile directory not found: {profile_path}")
        try:
            available = [d for d in os.listdir(user_data_dir) if os.path.isdir(os.path.join(user_data_dir, d))]
            logger.warning(f"Available profiles in {user_data_dir}: {available}")
        except Exception:
            pass

    # Use string command with shell=True for better Windows argument handling of special chars
    cmd = f'"{chrome_exe}" --remote-debugging-port={port} --user-data-dir="{user_data_dir}" --profile-directory="{profile_directory}"'
    
    logger.info(f"Launching Chrome command: {cmd}")
    proc = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def ensure_chrome_debug_ready(
    endpoint: str = CDP_ENDPOINT,
    chrome_exe: str = CHROME_EXE,
    user_data_dir: str = CHROME_USER_DATA_DIR,
    profile_directory: str = CHROME_PROFILE,
    timeout: int = 60,
) -> None:
    """Ensure Chrome is running with CDP debugging available.

    If the CDP endpoint is already reachable, does nothing.
    Otherwise, kills Chrome, relaunches with --remote-debugging-port, and waits.
    """
    if _is_cdp_ready(endpoint):
        logger.info("Chrome CDP endpoint already available")
        return

    logger.info("Chrome CDP not available — auto-launching...")

    # Extract port from endpoint
    port = 9222
    port_match = re.search(r":(\d+)$", endpoint.split("//")[-1])
    if port_match:
        port = int(port_match.group(1))

    # Kill existing Chrome (required for --remote-debugging-port to take effect)
    kill_chrome()

    # Launch fresh
    _launch_chrome_with_debugging(chrome_exe, user_data_dir, profile_directory, port)

    # Wait for CDP to become available
    logger.info("Waiting for Chrome to start...")
    start = time.time()
    while time.time() - start < timeout:
        if _is_cdp_ready(endpoint):
            logger.info("Chrome CDP is ready!")
            return
        time.sleep(1)

    raise ConnectionError(
        f"Chrome did not start with CDP on port {port} within {timeout}s. "
        f"Check that Chrome is installed at: {chrome_exe}"
    )


async def connect_cdp(endpoint: str = CDP_ENDPOINT) -> tuple[Browser, Page]:
    """Connect to Chrome via CDP and find the Novelpia tab.

    Returns (browser, page) where page is the Novelpia viewer tab.
    If no Novelpia tab is open, returns the first available tab.
    """
    if not _playwright:
        raise RuntimeError("Call start_playwright() first")

    try:
        browser = await _playwright.chromium.connect_over_cdp(endpoint)
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to Chrome at {endpoint}. Error: {e}"
        ) from e

    # Find the Novelpia/Pixiv viewer tab
    for context in browser.contexts:
        for page in context.pages:
            if (NOVELPIA_VIEWER_URL_PATTERN in page.url or 
                NOVELPIA_MAIN_URL_PATTERN in page.url or
                PIXIV_NOVEL_URL_PATTERN in page.url or
                PIXIV_SERIES_URL_PATTERN in page.url):
                logger.info(f"Found target tab: {page.url}")
                await page.bring_to_front()
                return browser, page

    # No Novelpia tab — return the first page (user can navigate manually)
    all_urls = []
    for context in browser.contexts:
        for page in context.pages:
            all_urls.append(page.url)
            if not page.url.startswith("chrome://"):
                logger.warning(
                    f"No Novelpia viewer tab found. Using first tab: {page.url}\n"
                    "  Please navigate to a Novelpia chapter in the browser."
                )
                await page.bring_to_front()
                return browser, page

    # All tabs are chrome:// — create a new one
    if browser.contexts:
        page = await browser.contexts[0].new_page()
        logger.warning("No usable tabs found. Created a new tab.")
        return browser, page

    raise ConnectionError(
        f"No usable browser tabs. Open tabs:\n"
        + "\n".join(f"  - {url}" for url in all_urls)
    )


async def launch_persistent(
    user_data_dir: str = CHROME_USER_DATA_DIR,
    start_url: str = "https://global.novelpia.com",
) -> tuple[BrowserContext, Page]:
    """Launch Chromium with a persistent profile. Requires Chrome to be fully closed.

    Returns (context, page) navigated to start_url.
    """
    if not _playwright:
        raise RuntimeError("Call start_playwright() first")
    
    # Use temporary profile to avoid directory locks and 'default directory' errors
    temp_dir = setup_temp_profile()

    logger.info(f"Launching persistent Chrome from: {temp_dir}")
    logger.info(f"Using executable: {CHROME_EXE}")
    
    try:
        context = await _playwright.chromium.launch_persistent_context(
            temp_dir,
            executable_path=CHROME_EXE,
            headless=False,
            channel="chrome",
            timeout=60000,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
    except Exception as e:
        logger.error(f"Failed to launch persistent context: {e}")
        raise

    page = context.pages[0] if context.pages else await context.new_page()

    if start_url:
        logger.info(f"Navigating to {start_url}")
        # Add a longer timeout and handle errors gracefully since Novelpia main can be slow
        try:
            await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning(f"Navigation to start URL timed out or failed: {e}")
            
    return context, page


async def wait_for_page_ready(page: Page) -> None:
    """Wait for the loading indicator to disappear and content to be visible."""
    
    # Pixiv doesn't use the Novelpia specific loading elements
    if PIXIV_NOVEL_URL_PATTERN in page.url or PIXIV_SERIES_URL_PATTERN in page.url:
        await asyncio.sleep(1) # Just give a brief moment for the page to settle
        return

    try:
        await page.wait_for_selector(
            SEL_LOADING_VIEW, state="hidden", timeout=LOADING_TIMEOUT_MS
        )
    except Exception:
        pass  # loading-view may not exist on this page

    try:
        selector = SEL_MAIN_NOVEL_DRAWING if NOVELPIA_MAIN_URL_PATTERN in page.url else SEL_VIEWER_CONTENTS
        await page.wait_for_selector(
            selector, state="visible", timeout=LOADING_TIMEOUT_MS
        )
    except Exception:
        logger.warning(f"{selector} not visible after timeout, proceeding anyway")

    await asyncio.sleep(0.5)


async def scroll_to_load_content(page: Page) -> None:
    """Slowly scroll the window top-to-bottom to trigger lazy loading, then back to top."""
    total_height = await page.evaluate("document.body.scrollHeight")
    current = 0

    # Scroll down
    while current < total_height:
        current += SCROLL_STEP_PX
        await page.evaluate(f"window.scrollTo(0, {current})")
        await asyncio.sleep(SCROLL_DELAY_MS / 1000)

    # Scroll back to top
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(0.5)


async def get_chapter_info(page: Page) -> dict:
    """Extract episode info from the page's Pinia/Nuxt state.

    Returns dict with keys: episode_no, epi_num, epi_title, next_episode_no, flag_type.
    Falls back to URL parsing if state extraction fails.
    """
    info = {"episode_no": "", "epi_num": 0, "epi_title": "", "next_episode_no": None, "flag_type": 0}

    # Try extracting from Pinia/Nuxt state
    try:
        # Check if page is still valid
        if page.is_closed():
            logger.warning("Page is closed, cannot extract info.")
            return info

        state = await page.evaluate("""() => {
            try {
                // Try Nuxt's useNuxtApp or __nuxt
                const nuxtApp = window.__nuxt_app__ || window.__NUXT__;
                if (nuxtApp && nuxtApp.state) {
                    // Search for episode data in Pinia stores
                    for (const [key, value] of Object.entries(nuxtApp.state)) {
                        if (value && value.episode_no) {
                            return {
                                episode_no: String(value.episode_no || ''),
                                epi_num: value.epi_num || 0,
                                epi_title: value.epi_title || '',
                                next_episode_no: value.next_epi ? String(value.next_epi.episode_no) : null,
                                flag_type: value.flag_type || 0,
                            };
                        }
                    }
                }

                // Try accessing Pinia stores from Vue app instance
                const app = document.querySelector('#__nuxt')?.__vue_app__;
                if (app) {
                    const pinia = app.config.globalProperties.$pinia;
                    if (pinia && pinia.state && pinia.state.value) {
                        for (const [key, store] of Object.entries(pinia.state.value)) {
                            if (store && store.next_epi) {
                                return {
                                    episode_no: String(store.episode_no || ''),
                                    epi_num: store.epi_num || 0,
                                    epi_title: store.epi_title || '',
                                    next_episode_no: store.next_epi ? String(store.next_epi.episode_no) : null,
                                    flag_type: store.flag_type || 0,
                                };
                            }
                        }
                    }
                }
            } catch (e) {
                return null;
            }
            return null;
        }""")

        if state:
            info.update(state)
            return info
    except Exception as e:
        logger.debug(f"State extraction (Global) failed: {e}")

    # Fallback 1: Extract from Main Novelpia DOM (novelpia.com)
    try:
        # Check if we are on the main site
        if NOVELPIA_MAIN_URL_PATTERN in page.url:
            # 1. Episode ID from URL or hidden input
            match = re.search(r"/viewer/(\d+)", page.url)
            if match:
                info["episode_no"] = match.group(1)

            # 2. Next episode ID from input containing the current URL pattern
            # Novelpia main uses inputs like <input type="hidden" value="/viewer/1114460">
            next_input = await page.evaluate(r"""() => {
                // Find all inputs that start with /viewer/ and return the first one that is NOT the current episode
                const inputs = Array.from(document.querySelectorAll('input[type="hidden"]'));
                for (const input of inputs) {
                    const val = input.value;
                    if (val && val.startsWith('/viewer/')) {
                        const nextId = val.split('/').pop();
                        // Assuming current ID is elsewhere in the DOM or URL
                        const currentId = window.location.pathname.split('/').pop();
                        if (nextId && nextId !== currentId) {
                            return nextId;
                        }
                    }
                }
                return null;
            }""")
            if next_input:
                info["next_episode_no"] = next_input

            # 3. Episode Title
            title_text = await page.evaluate("""() => {
                const line1 = document.querySelector('font.line[data-line="1"]');
                return line1 ? line1.innerText.trim() : document.title;
            }""")
            info["epi_title"] = title_text
            
            return info
            
    except Exception as e:
        logger.debug(f"Main site DOM extraction failed: {e}")

    # Fallback 2: parse episode_no from URL (if all else fails)
    try:
        match = re.search(r"/viewer/(\d+)", page.url)
        if match:
            info["episode_no"] = match.group(1)
    except Exception:
        pass

    return info


async def navigate_next_chapter(page: Page) -> bool:
    """Navigate to the next chapter. Returns True on success, False if no next chapter.

    Strategy:
    1. Try extracting next_epi.episode_no from Pinia store and navigate directly.
    2. Fall back to clicking the rightmost viewer-btn.
    """
    # Strategy 1: Pinia store navigation
    chapter_info = await get_chapter_info(page)
    next_ep = chapter_info.get("next_episode_no")

    if next_ep:
        if NOVELPIA_MAIN_URL_PATTERN in page.url:
            next_url = f"https://novelpia.com/viewer/{next_ep}"
        else:
            next_url = f"https://global.novelpia.com/viewer/{next_ep}"
            
        logger.info(f"  Navigating to next chapter via URL: {next_url}")
        
        # Wait for the page to navigate and fully replace its DOM
        try:
            await page.goto(next_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass # Timeout on network idle is okay as long as DOM changed
            
        delay = random.uniform(MIN_NAV_DELAY, MAX_NAV_DELAY)
        await asyncio.sleep(delay)
        await wait_for_page_ready(page)
        return True

    # Strategy 2: Click the next button
    logger.info("  Pinia state unavailable, trying button click...")
    try:
        buttons = await page.query_selector_all("div.viewer-bottom div.viewer-btn")
        if len(buttons) < 2:
            logger.warning("  Could not find navigation buttons")
            return False

        next_btn = buttons[-1]  # rightmost button

        # Check if disabled
        class_attr = await next_btn.get_attribute("class") or ""
        if "disabled" in class_attr:
            logger.info("  Next button is disabled — end of available chapters")
            return False

        # Wait for the navigation to trigger
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=10000):
                await next_btn.click()
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            logger.warning(f"  Wait for navigation state timed out, continuing: {e}")

        delay = random.uniform(MIN_NAV_DELAY, MAX_NAV_DELAY)
        await asyncio.sleep(delay)
        await wait_for_page_ready(page)
        return True

    except Exception as e:
        logger.error(f"  Navigation failed: {e}")
        return False
