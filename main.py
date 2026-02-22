"""
Novelpia Chapter Text Extractor

Usage (CDP mode — recommended):
    1. Start Chrome:
       chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\Users\\admin\\AppData\\Local\\Google\\Chrome\\User Data"
    2. Navigate to the chapter you want to start from.
    3. Run:
       python main.py

Usage (persistent mode):
    1. Close ALL Chrome windows.
    2. Run:
       python main.py --mode persistent --start-url https://global.novelpia.com/viewer/7832
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from config import (
    CDP_ENDPOINT,
    CHROME_USER_DATA_DIR,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_TRANSLATION_MODEL,
    MAX_CHAPTERS,
    OUTPUT_DIR,
    SEL_VIEWER_CONTENTS,
    OCR_PROMPT,
    TRANSLATION_PROMPT,
    TRANSLATION_DELAY,
)
from browser import (
    connect_cdp,
    launch_persistent,
    scroll_to_load_content,
    wait_for_page_ready,
    navigate_next_chapter,
    get_chapter_info,
    start_playwright,
    stop_playwright,
    ensure_chrome_debug_ready,
)
from ocr import create_gemini_client, refine_text_gemini, translate_text_gemini

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Novelpia Chapter Text Extractor")
    parser.add_argument(
        "--mode",
        choices=["cdp", "persistent"],
        default="persistent",
        help="Browser connection mode (default: persistent)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="Chrome remote debugging port (default: 9222)",
    )
    parser.add_argument(
        "--start-url",
        type=str,
        default=None,
        help="Starting chapter URL (optional for persistent mode)",
    )
    parser.add_argument(
        "--max-chapters",
        type=int,
        default=MAX_CHAPTERS,
        help=f"Maximum chapters to extract (default: {MAX_CHAPTERS})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    return parser.parse_args()


def save_chapter(output_dir: Path, chapter_id: str, chapter_index: int, text: str, suffix: str = "_Cleaned.txt") -> Path:
    """Save extracted text to a file. Returns the file path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"Chapter_{chapter_index:03d}_id{chapter_id}{suffix}"
    filepath = output_dir / filename
    filepath.write_text(text, encoding="utf-8")
    return filepath


async def extract_single_chapter(page, gemini_client, output_dir: Path, chapter_index: int) -> bool:
    """Extract text from the currently displayed chapter. Returns True on success."""
    chapter_info = await get_chapter_info(page)
    chapter_id = chapter_info["episode_no"] or "unknown"
    title = chapter_info.get("epi_title", "")

    logger.info(f"Chapter {chapter_index} (ID: {chapter_id}) {title}")

    # Scroll to trigger lazy loading
    await scroll_to_load_content(page)

    # Direct Text Extraction
    try:
        raw_text = await page.locator(SEL_VIEWER_CONTENTS).inner_text()
        logger.info(f"  Directly extracted {len(raw_text)} chars")
    except Exception as e:
        logger.error(f"  Extraction failed: {e}")
        return False

    if not raw_text or len(raw_text.strip()) < 50:
        logger.warning(f"  Extracted text is too short/empty for chapter {chapter_id}")
        return False

    # Refine with Gemini (Formatting/Cleanup)
    text = refine_text_gemini(gemini_client, raw_text, GEMINI_MODEL, OCR_PROMPT)

    # Save English Cleaned
    filepath = save_chapter(output_dir, chapter_id, chapter_index, text, suffix="_Cleaned.txt")
    logger.info(f"  Saved English: {filepath.name} ({len(text)} chars)")

    # Translate to Vietnamese (Gemini 1.5 Pro)
    logger.info("  Translating to Vietnamese...")
    vietnamese_text = translate_text_gemini(gemini_client, text, GEMINI_TRANSLATION_MODEL, TRANSLATION_PROMPT)
    
    # Save Vietnamese Translation
    viet_filepath = save_chapter(output_dir, chapter_id, chapter_index, vietnamese_text, suffix="_Vietnamese_LN.txt")
    logger.info(f"  Saved Vietnamese: {viet_filepath.name}")

    # Rate Limit Cool-down
    logger.info(f"  Cooling down for {TRANSLATION_DELAY}s to respect Gemini API limits...")
    await asyncio.sleep(TRANSLATION_DELAY)

    return True


async def main_loop(args: argparse.Namespace) -> None:
    """Main orchestration loop."""
    if not GEMINI_API_KEY:
        sys.exit("Error: GEMINI_API_KEY not set. Create a .env file with your key.")

    gemini_client = create_gemini_client(GEMINI_API_KEY)
    logger.info("Gemini client initialized")

    await start_playwright()
    browser_handle = None  # Browser or BrowserContext to clean up

    try:
        # Connect to browser
        if args.mode == "cdp":
            endpoint = f"http://127.0.0.1:{args.port}"
            # Ensure Chrome is running with debugging
            try:
                ensure_chrome_debug_ready(endpoint=endpoint)
            except Exception as e:
                sys.exit(f"Failed to launch/connect to Chrome: {e}")

            browser, page = await connect_cdp(endpoint)
            browser_handle = browser
            logger.info(f"Connected via CDP to: {page.url}")
        else:
            # Persistent mode (default)
            # launch_persistent handles kill_chrome internally now
            context, page = await launch_persistent(CHROME_USER_DATA_DIR, args.start_url)
            browser_handle = context
            logger.info(f"Launched persistent browser at: {page.url}")

        print("\n" + "=" * 50)
        print("Browser is ready.")
        print("1. If this is your first run, please LOG IN to Novelpia now.")
        print("2. Navigate to the starting chapter.")
        print("3. Wait for the chapter content to load.")
        input("Press Enter to start extraction...")
        print("=" * 50 + "\n")

        await wait_for_page_ready(page)

        # Extraction loop
        extracted = 0
        for chapter_index in range(1, args.max_chapters + 1):
            try:
                success = await extract_single_chapter(
                    page, gemini_client, args.output_dir, chapter_index
                )
                if success:
                    extracted += 1

            except Exception as e:
                error_msg = str(e).lower()
                if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
                    logger.warning(f"Gemini rate limit hit. Waiting 60s before retry...")
                    await asyncio.sleep(60)
                    try:
                        success = await extract_single_chapter(
                            page, gemini_client, args.output_dir, chapter_index
                        )
                        if success:
                            extracted += 1
                    except Exception as retry_err:
                        logger.error(f"Retry failed: {retry_err}")
                        break
                else:
                    logger.error(f"Error on chapter {chapter_index}: {e}")
                    break

            # Navigate to next chapter (unless this was the last one)
            if chapter_index < args.max_chapters:
                has_next = await navigate_next_chapter(page)
                if not has_next:
                    logger.info("No next chapter available. Stopping.")
                    break

        logger.info(f"Done. Extracted {extracted} chapter(s) to {args.output_dir}")

    finally:
        # Cleanup
        if browser_handle:
            if args.mode == "cdp":
                # For CDP, we just want to disconnect without closing the browser.
                # Stopping playwright (below) handles the pipe closure.
                pass
            else:
                try:
                    await browser_handle.close()
                except Exception:
                    pass

        await stop_playwright()


def main():
    args = parse_args()
    asyncio.run(main_loop(args))


if __name__ == "__main__":
    main()
