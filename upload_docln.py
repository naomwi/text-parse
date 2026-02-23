import asyncio
import argparse
import re
import time
from pathlib import Path
from playwright.async_api import async_playwright
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent / "output" / "temp_profile"
EXECUTABLE_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def parse_args():
    parser = argparse.ArgumentParser(description="Upload extracted novel chapters to docln.sbs")
    parser.add_argument("--novel-dir", type=str, required=True, help="Path to the directory containing the extracted chapter text files (.txt)")
    parser.add_argument("--book-id", type=str, required=True, help="The Book (Volume) ID on docln.sbs (e.g. 35371)")
    parser.add_argument("--suffix", type=str, default="_Cleaned.txt", help="File suffix to filter chapters. Default: _Cleaned.txt")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay in seconds between uploads to avoid spamming the server")
    return parser.parse_args()


def parse_chapter_info_from_filename(filename: str) -> tuple[int, str]:
    """Parse chapter number and formatted title from the filename."""
    # Example: Chapter_133_Patrol_With_Good_Intentions_id7733_Cleaned.txt
    match = re.match(r"^Chapter_(\d+)_?(.*?)_id", filename)
    if not match:
        return -1, ""
    
    chapter_num = int(match.group(1))
    title_part = match.group(2).replace("_", " ").strip()
    
    if title_part:
        chapter_title = f"Chương {chapter_num} - {title_part}"
    else:
        chapter_title = f"Chương {chapter_num}"
        
    return chapter_num, chapter_title


def format_text_to_html(raw_text: str) -> str:
    """Wrap paragraphs in <p> tags for the Tiptap editor."""
    lines = raw_text.split("\n")
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<p><br></p>")
        else:
            # Escape basic HTML chars to prevent injection issues if the novel text contains < or >
            line = line.replace("<", "&lt;").replace(">", "&gt;")
            html_lines.append(f"<p>{line}</p>")
    return "".join(html_lines)


async def main_loop(args):
    novel_dir = Path(args.novel_dir)
    if not novel_dir.exists() or not novel_dir.is_dir():
        logger.error(f"Directory not found: {novel_dir}")
        return

    # 1. Collect and sort files
    chapter_files = []
    for f in novel_dir.glob(f"*{args.suffix}"):
        num, title = parse_chapter_info_from_filename(f.name)
        if num >= 0:
            chapter_files.append((num, title, f))
            
    # Sort files sequentially by chapter number
    chapter_files.sort(key=lambda x: x[0])
    
    if not chapter_files:
        logger.error(f"No files matching suffix '{args.suffix}' found in {novel_dir}")
        return
        
    logger.info(f"Found {len(chapter_files)} chapters to upload.")

    # 2. Start Playwright
    logger.info(f"Launching persistent Chrome profile...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=EXECUTABLE_PATH,
            headless=False, # Keep visible to monitor the uploads
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        # Check Login Status optionally by navigating to dashboard
        logger.info("Verifying session on docln.sbs...")
        await page.goto("https://docln.sbs/action", wait_until="domcontentloaded")
        
        # Simple check if there's a login button or if we are redirected to login
        if "login" in page.url or await page.query_selector('a[href*="login"]'):
            logger.error("Session is not logged in! Please manually log into docln.sbs on the opened browser.")
            input("Press Enter here in the console AFTER you have successfully logged in...")
            
        logger.info("Session verified. Beginning upload sequence.")
        
        upload_count = 0
        for num, title, filepath in chapter_files:
            logger.info(f"Uploading Chapter {num}: {title}...")
            
            raw_text = filepath.read_text(encoding="utf-8")
            html_content = format_text_to_html(raw_text)
            
            try:
                # 1. Navigate to Chapter Creation Page
                create_url = f"https://docln.sbs/action/chapter/create/book={args.book_id}"
                await page.goto(create_url, wait_until="networkidle")
                
                # Verify we are on the creation page
                if "create" not in page.url:
                    logger.error(f"Failed to reach chapter creation page. Current URL: {page.url}. Did the volume ID change?")
                    continue
                
                # 2. Fill Title
                await page.fill('input[name="title"]', title)
                
                # 3. Inject Content into Tiptap (ProseMirror)
                # We can inject directly into the contenteditable ProseMirror div
                await page.evaluate(f"""(htmlString) => {{
                    const editor = document.querySelector('.ProseMirror');
                    if (editor) {{
                        editor.innerHTML = htmlString;
                    }} else {{
                        // Fallback to text area if ProseMirror is slow to load or changed
                        const textarea = document.getElementById('LN_Chapter_Content');
                        if (textarea) textarea.value = htmlString;
                    }}
                }}""", html_content)
                
                # Optionally trigger input event just in case Tiptap needs it
                await page.evaluate("() => { const el = document.querySelector('.ProseMirror'); if(el) el.dispatchEvent(new Event('input', {bubbles: true})); }")
                
                # 4. Submit
                logger.debug(f"Submitting chapter...")
                # The generic submit button form
                await page.click('button:has-text("Thêm chương")')
                
                # Wait for the navigation after submitting (usually redirects to the chapter edit page or list)
                await page.wait_for_load_state("domcontentloaded")
                
                logger.info(f"✓ Uploaded {filepath.name} successfully.")
                upload_count += 1
                
                # 5. Cooldown
                logger.debug(f"Waiting {args.delay} seconds before next upload...")
                await asyncio.sleep(args.delay)
                
            except Exception as e:
                logger.error(f"Failed to upload {filepath.name}: {e}")
                logger.info("Will attempt to continue with the next chapter after a delay.")
                await asyncio.sleep(args.delay)

        logger.info(f"Done! Successfully uploaded {upload_count}/{len(chapter_files)} chapters.")
        await context.close()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main_loop(args))
    except KeyboardInterrupt:
        print("\n\n[INFO] Upload stopped by user.")
