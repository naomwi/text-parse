import logging
import re
from typing import Dict, Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def fetch_pixiv_novel(page: Page, novel_id: str) -> Dict[str, Any]:
    """Fetch novel data directly from Pixiv's internal AJAX API using the browser's cookies."""
    api_url = f"https://www.pixiv.net/ajax/novel/{novel_id}"
    logger.info(f"Fetching Pixiv novel metadata from API: {api_url}")
    
    # We use page.request.get to automatically inherit the user's cookies and user-agent
    response = await page.request.get(api_url)
    if not response.ok:
        raise Exception(f"Pixiv API request failed with status {response.status}: {response.status_text}")
        
    data = await response.json()
    if data.get("error"):
        error_msg = data.get("message", "Unknown API error")
        raise Exception(f"Pixiv API returned an error: {error_msg}")
        
    return data.get("body", {})


async def fetch_pixiv_series_content(page: Page, series_id: str, limit: int = 100) -> list[dict]:
    """Fetch the list of episode IDs and titles for a given series."""
    api_url = f"https://www.pixiv.net/ajax/novel/series/{series_id}/content_titles?limit={limit}&last_order=0&order_by=asc"
    logger.info(f"Fetching Pixiv series episodes list from API: {api_url}")
    
    response = await page.request.get(api_url)
    if not response.ok:
        raise Exception(f"Pixiv Series API request failed with status {response.status}: {response.status_text}")
        
    data = await response.json()
    if data.get("error"):
        error_msg = data.get("message", "Unknown API error")
        raise Exception(f"Pixiv Series API returned an error: {error_msg}")
        
    return data.get("body", [])


def format_pixiv_text(raw_text: str) -> str:
    """
    Parse Pixiv's custom markup tags into plain readable text.
    
    Handles:
    - [newpage] -> Page break
    - [[rb:TEXT > READING]] -> TEXT
    - [chapter:TITLE] -> TITLE
    - [uploadedimage:ID] / [pixivimage:ID] -> Image placeholders
    """
    if not raw_text:
        return ""
        
    text = raw_text
    
    # 1. Page breaks
    text = text.replace("[newpage]", "\n\n--- PAGE BREAK ---\n\n")
    
    # 2. Section Headings [chapter:TITLE] -> ### TITLE
    text = re.sub(r'\[chapter:(.*?)\]', r'\n\n### \1\n\n', text)
    
    # 3. Ruby text / Furigana
    # Format: [[rb:漢字 > かんじ]]
    # We will strip the ruby reading and keep just the base text since humans don't need it 
    # for translation, and Gemini handles context well anyway.
    text = re.sub(r'\[\[rb:(.*?) > .*?\]\]', r'\1', text)
    
    # 4. Images
    text = re.sub(r'\[uploadedimage:.*?\]', r'[IMAGE]', text)
    text = re.sub(r'\[pixivimage:.*?\]', r'[IMAGE]', text)
    
    # Ensure uniform newlines and strip excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
