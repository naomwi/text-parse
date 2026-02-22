"""Configuration constants and environment loading for Novelpia extractor."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DATA_DIR = r"C:\Users\admin\AppData\Local\Google\Chrome\User Data"
CHROME_PROFILE = "Default"
OUTPUT_DIR = Path(__file__).parent / "output"
TEMP_PROFILE_DIR = OUTPUT_DIR / "temp_profile"

# --- Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TRANSLATION_MODEL = "gemini-2.5-pro"

# --- Extraction ---
MAX_CHAPTERS = 50
SCREENSHOT_SEGMENT_HEIGHT = 4000  # px threshold before splitting
SCREENSHOT_VIEWPORT_HEIGHT = 3000  # px per segment capture

# --- Timing ---
TRANSLATION_DELAY = 25  # Seconds to wait between chapters to avoid Rate Limits
MIN_NAV_DELAY = 2.0
MAX_NAV_DELAY = 3.0
SCROLL_STEP_PX = 500
SCROLL_DELAY_MS = 100
LOADING_TIMEOUT_MS = 15000

# --- Browser (Global Site) ---
CDP_ENDPOINT = "http://127.0.0.1:9222"
NOVELPIA_VIEWER_URL_PATTERN = "global.novelpia.com/viewer"

# --- DOM Selectors (Global Site) ---
SEL_VIEWER_CONTENTS = "div.viewer-contents"
SEL_VIEWER_WRAPPER = "div.viewer-contents-wrapper"
SEL_NAV_BUTTONS = "div.viewer-bottom div.viewer-btn"
SEL_LOADING_VIEW = ".loading-view"
SEL_STICKY_BOTTOM = "div.viewer-bottom"
SEL_STICKY_HEADER = "div.viewer-header-container"

# --- Browser & Selectors (Main Site) ---
NOVELPIA_MAIN_URL_PATTERN = "novelpia.com/viewer"
NOVELPIA_SERIES_URL_PATTERN = "novelpia.com/novel/"
NOVELPIA_API_EPISODE_LIST = "https://novelpia.com/proc/episode_list"

SEL_MAIN_NOVEL_DRAWING = "#novel_drawing"
SEL_MAIN_FONT_LINE = "#novel_drawing font.line"

# --- Browser & Selectors (Pixiv) ---
PIXIV_NOVEL_URL_PATTERN = "pixiv.net/novel/show.php"
PIXIV_SERIES_URL_PATTERN = "pixiv.net/novel/series/"
PIXIV_API_NOVEL = "https://www.pixiv.net/ajax/novel/{}"
PIXIV_API_SERIES = "https://www.pixiv.net/ajax/novel/series/{}"
PIXIV_API_SERIES_CONTENT = "https://www.pixiv.net/ajax/novel/series/{}/content_titles?limit=100&last_order=0&order_by=asc"

# --- Local OCR ---
OCR_LANGUAGES = ["en"]

# --- Gemini OCR Refinement Prompt ---
OCR_PROMPT = (
    "Below is raw OCR text from a novel. Please clean it up by: "
    "1) Fixing obvious typos or character misidentifications, "
    "2) Removing non-story elements like UI buttons, timestamps, or translator comments, "
    "3) Ensuring proper paragraph spacing. "
    "Do not change the story content, only fix the formatting and errors."
)

# --- Translation Prompt ---
TRANSLATION_PROMPT = """Chỉ thị dịch thuật:

Vai trò: Bạn là một biên dịch viên Light Novel chuyên nghiệp, am hiểu sâu sắc về văn hóa anime/manga.

Nhiệm vụ: Dịch văn bản tiếng Anh sau đây sang tiếng Việt.

Yêu cầu phong cách (LN Style):

Văn phong: Sử dụng từ ngữ giàu cảm xúc, bay bổng nhưng vẫn dễ hiểu. Ưu tiên cách diễn đạt gãy gọn, tạo nhịp điệu cho câu văn.

Xưng hô: Tùy biến linh hoạt (Tôi - Bạn, Cậu - Tớ, Anh - Em...) dựa trên ngữ cảnh và tính cách nhân vật. Tránh dùng 'nó' một cách máy móc.

Từ láy & Biểu cảm: Tích hợp các từ láy và các từ ngữ gợi hình để làm nổi bật tâm trạng nhân vật hoặc bầu không khí trong truyện.

Tự nhiên hóa: Chuyển đổi các câu đùa, thành ngữ tiếng Anh sang các cách nói tương đương trong tiếng Việt sao cho tự nhiên nhất, không dịch word-by-word."""
