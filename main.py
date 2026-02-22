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
import re
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
    NOVELPIA_MAIN_URL_PATTERN,
    NOVELPIA_SERIES_URL_PATTERN,
    PIXIV_NOVEL_URL_PATTERN,
    PIXIV_SERIES_URL_PATTERN,
    SEL_MAIN_NOVEL_DRAWING,
    SEL_MAIN_FONT_LINE,
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
from novelpia import fetch_novelpia_series_episodes
from pixiv import fetch_pixiv_novel, fetch_pixiv_series_content, format_pixiv_text
from ocr import create_gemini_client, refine_text_gemini, translate_text_gemini, extract_text_hybrid
from screenshot import capture_element_screenshots

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
        "--chapters",
        "--max-chapters",
        dest="max_chapters",
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
    parser.add_argument(
        "--translate",
        action="store_true",
        help="Enable Vietnamese translation (default: False)",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run in GUI mode (skips the Enter to start prompt)",
    )
    return parser.parse_args()


def save_chapter(output_dir: Path, chapter_id: str, chapter_index: int, title: str, text: str, novel_name: str = None, suffix: str = "_Cleaned.txt") -> Path:
    """Save extracted text to a file. Returns the file path."""
    
    # Create the novel-specific subfolder
    if novel_name:
        safe_novel_name = re.sub(r'[\\/*?:"<>|]', "", novel_name).strip()
        if len(safe_novel_name) > 100:
            safe_novel_name = safe_novel_name[:100]
        save_dir = output_dir / safe_novel_name
    else:
        save_dir = output_dir

    save_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title for Windows filename
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    safe_title = safe_title.replace(" ", "_").strip()
    if len(safe_title) > 50:
        safe_title = safe_title[:50]
        
    filename = f"Chapter_{chapter_index:03d}_{safe_title}_id{chapter_id}{suffix}"
    filepath = save_dir / filename
    filepath.write_text(text, encoding="utf-8")
    return filepath


async def extract_single_chapter(page, gemini_client, output_dir: Path, chapter_index: int, translate: bool = False) -> tuple[bool, str]:
    """Extract text from the currently displayed chapter. Returns (Success, NovelFolderName)."""
    
    # Check if this is a Pixiv novel
    is_pixiv = PIXIV_NOVEL_URL_PATTERN in page.url
    
    if is_pixiv:
        # Pixiv API extraction (bypasses all Novelpia DOM logic)
        match = re.search(r"id=(\d+)", page.url)
        if not match:
            logger.error("Could not find Pixiv novel ID in URL")
            return False, "Unknown_Pixiv_Novel"
            
        novel_id = match.group(1)
        logger.info(f"Chapter {chapter_index} (Pixiv ID: {novel_id})")
        
        try:
            pixiv_data = await fetch_pixiv_novel(page, novel_id)
            title = pixiv_data.get("title", f"Pixiv_{novel_id}")
            logger.info(f"  Fetched API metadata for: {title}")
            
            # Use series title if available, else use this novel's title
            novel_name = title
            series_data = pixiv_data.get("seriesNavData")
            if series_data and "title" in series_data:
                novel_name = series_data["title"]
            
            raw_text = pixiv_data.get("content", "")
            text = format_pixiv_text(raw_text)
            
            logger.info(f"  Formatted Pixiv text: {len(text)} chars")
            
        except Exception as e:
            logger.error(f"  Pixiv extraction failed: {e}")
            return False, "Unknown_Pixiv_Novel"
            
        chapter_id = novel_id
        
    else:
        # Standard Novelpia Extraction
        chapter_info = await get_chapter_info(page)
        chapter_id = chapter_info["episode_no"] or "unknown"
        title = chapter_info.get("epi_title", "")
        
        # Try to parse novel name from the <title> tag
        # Usually Novelpia viewer title is: "0 - 프롤로그 - 악녀로 끝나는 세계 - 웹소설"
        page_title = await page.title()
        parts = page_title.split(" - ")
        novel_name = parts[-2] if len(parts) >= 3 else f"Novelpia_{chapter_id}"

        logger.info(f"Chapter {chapter_index} (ID: {chapter_id}) {title} - Series: {novel_name}")

        # Scroll to trigger lazy loading
        await scroll_to_load_content(page)

        # Direct Text Extraction
        try:
            if NOVELPIA_MAIN_URL_PATTERN in page.url:
                # Main site extraction (strip hidden <p> tags with base64 tokens)
                extracted_data = await page.evaluate(f"""() => {{
                const lines = Array.from(document.querySelectorAll('{SEL_MAIN_FONT_LINE}'));
                let text = [];
                let firstLineId = "none";
                let lastLineId = "none";
                
                if (lines.length > 0) {{
                    firstLineId = lines[0].getAttribute('data-line') || "none";
                    lastLineId = lines[lines.length - 1].getAttribute('data-line') || "none";
                }}
                
                for (const line of lines) {{
                    // Clone the node so we don't modify the actual DOM
                    const clone = line.cloneNode(true);
                    
                    // Remove all <p> tags (anti-scraping tokens)
                    const ps = clone.querySelectorAll('p');
                    ps.forEach(p => p.remove());
                    
                    const lineText = clone.innerText.trim();
                    if (lineText) {{
                        text.push(lineText);
                    }} else {{
                        // Empty line (usually spacers) acts as paragraph break
                        text.push('');
                    }}
                }}
                
                return {{
                    count: lines.length,
                    first_line: firstLineId,
                    last_line: lastLineId,
                    text: text.join('\\n')
                }};
            }}""")
            
                raw_text = extracted_data["text"]
                logger.info(f"  [DEBUG] Found {extracted_data['count']} line elements. First data-line: {extracted_data['first_line']}, Last data-line: {extracted_data['last_line']}")

            else:
                # Global site extraction
                raw_text = await page.locator(SEL_VIEWER_CONTENTS).inner_text()
                
            logger.info(f"  Directly extracted {len(raw_text)} chars")
        except Exception as e:
            logger.error(f"  Extraction failed: {e}")
            raw_text = ""

    text = ""
    # Only try OCR fallback if NOT Pixiv, since Pixiv API guarantees text if successful
    if not is_pixiv and (not raw_text or len(raw_text.strip()) < 50):
        logger.warning(f"  Extracted text is too short/empty for chapter {chapter_id}. Falling back to OCR...")
        
        # OCR Fallback
        try:
            selector = SEL_MAIN_NOVEL_DRAWING if NOVELPIA_MAIN_URL_PATTERN in page.url else SEL_VIEWER_CONTENTS
            segments = await capture_element_screenshots(page, selector)
            if segments:
                logger.info(f"  Captured {len(segments)} segments for OCR")
                text = extract_text_hybrid(gemini_client, segments, GEMINI_MODEL, OCR_PROMPT)
            else:
                logger.error("  Screenshot capture returned no segments.")
                return False, novel_name
        except Exception as e:
            logger.error(f"  OCR fallback failed: {e}")
            return False, novel_name
            
    if not text:
        # Refine with Gemini (Formatting/Cleanup) if direct extraction worked
        # (For Pixiv, text is already set above to format_pixiv_text, so it bypasses Gemini refine!)
        if is_pixiv:
            text = raw_text # Pixiv text is already clean-ish, but format_pixiv_text stripped the brackets
        else:
            text = refine_text_gemini(gemini_client, raw_text, GEMINI_MODEL, OCR_PROMPT)

    # Save English/Cleaned
    filepath = save_chapter(output_dir, chapter_id, chapter_index, title, text, novel_name=novel_name, suffix="_Cleaned.txt")
    logger.info(f"  Saved Cleaned Text: {filepath.name} ({len(text)} chars)")

    if translate:
        # Translate to Vietnamese (Gemini 1.5 Pro)
        logger.info("  Translating to Vietnamese...")
        vietnamese_text = translate_text_gemini(gemini_client, text, GEMINI_TRANSLATION_MODEL, TRANSLATION_PROMPT)
        
        # Save Vietnamese Translation
        viet_filepath = save_chapter(output_dir, chapter_id, chapter_index, title, vietnamese_text, novel_name=novel_name, suffix="_Vietnamese_LN.txt")
        logger.info(f"  Saved Vietnamese: {viet_filepath.name}")

    # Rate Limit Cool-down
    logger.info(f"  Cooling down for {TRANSLATION_DELAY}s to respect Gemini API limits...")
    await asyncio.sleep(TRANSLATION_DELAY)

    return True, novel_name


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

        logger.info("Browser is ready.")
        logger.info("1. If this is your first run, please LOG IN to Novelpia now.")
        logger.info("2. Navigate to the starting chapter.")
        logger.info("3. Wait for the chapter content to load.")
        if not getattr(args, "gui", False):
            input("Press Enter to start extraction...")

        await wait_for_page_ready(page)
        
        # Check if navigating a Pixiv or Novelpia Series vs a single chapter
        is_pixiv_series = PIXIV_SERIES_URL_PATTERN in page.url
        is_novelpia_series = NOVELPIA_SERIES_URL_PATTERN in page.url
        
        pixiv_series_episodes = []
        novelpia_series_episodes = []
        
        if is_pixiv_series:
            match = re.search(r"series/(\d+)", page.url)
            if match:
                series_id = match.group(1)
                try:
                    logger.info(f"Detected Pixiv series: {series_id}. Fetching episode list...")
                    pixiv_series_episodes = await fetch_pixiv_series_content(page, series_id, limit=args.max_chapters)
                    logger.info(f"Found {len(pixiv_series_episodes)} available episodes in the series.")
                    
                    # Ensure we are actually on an individual novel page to start extraction
                    if pixiv_series_episodes:
                        first_ep_id = pixiv_series_episodes[0]["id"]
                        first_url = f"https://www.pixiv.net/novel/show.php?id={first_ep_id}"
                        logger.info(f"Navigating to first episode: {first_url}")
                        await page.goto(first_url)
                        await wait_for_page_ready(page)
                except Exception as e:
                    logger.error(f"Failed to fetch Pixiv series episodes: {e}")
            else:
                logger.error("Could not find series ID in Pixiv URL.")
                
        elif is_novelpia_series:
            match = re.search(r"novel/(\d+)", page.url)
            if match:
                novel_no = match.group(1)
                try:
                    logger.info(f"Detected Novelpia series: {novel_no}. Fetching episode list...")
                    novelpia_series_episodes = await fetch_novelpia_series_episodes(page, novel_no, limit=args.max_chapters)
                    logger.info(f"Found {len(novelpia_series_episodes)} episodes in the series.")
                    
                    if novelpia_series_episodes:
                        first_ep_id = novelpia_series_episodes[0]
                        first_url = f"https://novelpia.com/viewer/{first_ep_id}"
                        logger.info(f"Navigating to first episode: {first_url}")
                        await page.goto(first_url)
                        await wait_for_page_ready(page)
                except Exception as e:
                    logger.error(f"Failed to fetch Novelpia series episodes: {e}")
            else:
                logger.error("Could not find novel_no in Novelpia URL.")

        # Extraction loop
        extracted = 0
        for chapter_index in range(1, args.max_chapters + 1):
            try:
                success = await extract_single_chapter(
                    page, gemini_client, args.output_dir, chapter_index, translate=args.translate
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
                            page, gemini_client, args.output_dir, chapter_index, translate=args.translate
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
                if is_pixiv_series and chapter_index < len(pixiv_series_episodes):
                    next_ep = pixiv_series_episodes[chapter_index]  # chapter_index is 1-based, so this gets the next item
                    if next_ep.get("available", False):
                        next_url = f"https://www.pixiv.net/novel/show.php?id={next_ep['id']}"
                        logger.info(f"  Navigating to next Pixiv chapter in series: {next_url}")
                        await page.goto(next_url)
                        await asyncio.sleep(2)  # Give Pixiv API time to chill
                        await wait_for_page_ready(page)
                    else:
                        logger.warning(f"  Next Pixiv episode {next_ep['id']} is unavailable/deleted.")
                        break
                        
                elif is_novelpia_series and chapter_index < len(novelpia_series_episodes):
                    # Uses internal list instead of relying on Pinia state/Buttons which might fail
                    next_ep_id = novelpia_series_episodes[chapter_index]
                    next_url = f"https://novelpia.com/viewer/{next_ep_id}"
                    logger.info(f"  Navigating to next Novelpia chapter in series list: {next_url}")
                    
                    try:
                        await page.goto(next_url, wait_until="domcontentloaded")
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                        
                    await asyncio.sleep(2) 
                    await wait_for_page_ready(page)
                        
                elif PIXIV_NOVEL_URL_PATTERN in page.url and not is_pixiv_series:
                    # Single Pixiv novel, no series info provided
                    logger.info("Single Pixiv novel finished execution. Provide a Series URL to extract bulk chapters.")
                    break
                    
                else:
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
