"""Screenshot capture with segmentation for long chapters."""

import asyncio
import logging
import math

from playwright.async_api import Page

from config import (
    SCREENSHOT_SEGMENT_HEIGHT,
    SCREENSHOT_VIEWPORT_HEIGHT,
    SEL_STICKY_BOTTOM,
    SEL_STICKY_HEADER,
    SEL_VIEWER_CONTENTS,
)

logger = logging.getLogger(__name__)

# Elements to hide during screenshots (sticky overlays)
_HIDE_SELECTORS = [SEL_STICKY_BOTTOM, SEL_STICKY_HEADER]


async def _hide_overlays(page: Page) -> None:
    """Hide sticky header and bottom bar to prevent overlay in screenshots."""
    for sel in _HIDE_SELECTORS:
        await page.evaluate(
            f"document.querySelector('{sel}')?.style.setProperty('display', 'none', 'important')"
        )


async def _restore_overlays(page: Page) -> None:
    """Restore hidden sticky elements."""
    for sel in _HIDE_SELECTORS:
        await page.evaluate(
            f"document.querySelector('{sel}')?.style.removeProperty('display')"
        )


async def _get_element_metrics(page: Page, selector: str) -> dict:
    """Get element's position and dimensions on the page.

    Returns dict with: top, left, width, height (all in page coordinates).
    """
    metrics = await page.evaluate(f"""() => {{
        const el = document.querySelector('{selector}');
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        return {{
            top: rect.top + window.scrollY,
            left: rect.left + window.scrollX,
            width: rect.width,
            height: el.scrollHeight || rect.height,
        }};
    }}""")

    if not metrics:
        raise ValueError(f"Element not found: {selector}")

    return metrics


async def capture_element_screenshots(
    page: Page,
    selector: str = SEL_VIEWER_CONTENTS,
) -> list[bytes]:
    """Capture screenshot(s) of the chapter content element.

    For short content (<= SCREENSHOT_SEGMENT_HEIGHT px), takes a single element screenshot.
    For long content, scrolls and captures in SCREENSHOT_VIEWPORT_HEIGHT px segments.

    Returns a list of PNG byte buffers (one or more).
    """
    await _hide_overlays(page)

    try:
        metrics = await _get_element_metrics(page, selector)
        element_height = metrics["height"]
        logger.info(f"  Content height: {element_height:.0f}px")

        if element_height <= SCREENSHOT_SEGMENT_HEIGHT:
            # Short chapter — single element screenshot
            element = await page.query_selector(selector)
            if not element:
                raise ValueError(f"Element not found: {selector}")

            screenshot = await element.screenshot(type="png")
            return [screenshot]

        # Long chapter — segmented capture
        logger.info(
            f"  Long chapter detected ({element_height:.0f}px), "
            f"splitting into segments of {SCREENSHOT_VIEWPORT_HEIGHT}px"
        )

        segments = []
        num_segments = math.ceil(element_height / SCREENSHOT_VIEWPORT_HEIGHT)
        element_top = metrics["top"]
        element_left = metrics["left"]
        element_width = metrics["width"]

        for i in range(num_segments):
            offset = i * SCREENSHOT_VIEWPORT_HEIGHT
            remaining = element_height - offset
            seg_height = min(SCREENSHOT_VIEWPORT_HEIGHT, remaining)

            # Scroll so this segment is at the top of the viewport
            scroll_y = element_top + offset
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(0.2)

            # Capture with clip region (coordinates relative to viewport)
            screenshot = await page.screenshot(
                type="png",
                clip={
                    "x": element_left,
                    "y": 0,
                    "width": element_width,
                    "height": seg_height,
                },
            )
            segments.append(screenshot)
            logger.info(f"    Segment {i + 1}/{num_segments} captured ({seg_height:.0f}px)")

        return segments

    finally:
        await _restore_overlays(page)
