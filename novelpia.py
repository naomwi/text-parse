import logging
import re
from typing import List

from playwright.async_api import Page

from config import NOVELPIA_API_EPISODE_LIST

logger = logging.getLogger(__name__)


async def fetch_novelpia_series_episodes(page: Page, novel_no: str, limit: int = 100) -> List[str]:
    """
    Fetch the list of episode IDs for a given Novelpia Series using the pagination API.
    Returns a list of string episode IDs (e.g. ['local_1', '1114367', ...])
    """
    logger.info(f"Fetching Novelpia series episodes list from API: {NOVELPIA_API_EPISODE_LIST}")
    
    episode_ids = []
    page_num = 0
    
    # The API returns 20 items per page
    # Keep fetching until we hit the requested max limit, or run out of pages.
    while len(episode_ids) < limit:
        logger.info(f"  Fetching series page {page_num}...")
        
        # This endpoint uses standard application/x-www-form-urlencoded
        response = await page.request.post(
            NOVELPIA_API_EPISODE_LIST,
            form={
                "novel_no": novel_no,
                "sort": "UP", # Ascending order (oldest to newest)
                "page": str(page_num)
            }
        )
        
        if not response.ok:
            logger.error(f"Novelpia Series API request failed with status {response.status}: {response.status_text}")
            break
            
        html_content = await response.text()
        
        # The DOM is a table tr list. We simply regex the data-episode-no parameter
        # Format: <tr class="ep_style5" data-episode-no="1114367">
        matches = re.findall(r'data-episode-no="([^"]+)"', html_content)
        
        if not matches:
            break # No more episodes on this page
            
        for ep_id in matches:
            if ep_id not in episode_ids:
                episode_ids.append(ep_id)
                if len(episode_ids) >= limit:
                    break
        
        page_num += 1
        
    return episode_ids
