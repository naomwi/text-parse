import asyncio
from playwright.async_api import async_playwright
import re

async def run():
    p = await async_playwright().start()
    b = await p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    page = await b.new_page()
    await page.goto('https://novelpia.com/viewer/1114460')
    await page.wait_for_timeout(3000)
    
    val = await page.evaluate('''() => {
        // Find the title element. It's usually the first font.line element, or inside a b/font_18 tag.
        // We'll look for the first element with text that isn't a random UI string
        const ignoreList = ['장', '원', '×', '정기구독', '휴대폰', '신용카드', 'im miy', 'im my'];
        
        let possibleTitles = [];
        
        // 1. Try first font.line
        const lines = document.querySelectorAll('font.line');
        if (lines.length > 0) {
            let t = lines[0].innerText.trim();
            if (t && !ignoreList.some(i => t.includes(i))) {
                possibleTitles.push({source: 'font.line', text: t});
            }
        }
        
        // 2. Try the viewer-title span which holds the proper title on some pages
        const titleSpan = document.querySelector('.viewer-title');
        if (titleSpan) {
            let t = titleSpan.innerText.trim();
            if (t && !ignoreList.some(i => t.includes(i))) {
                possibleTitles.push({source: 'viewer-title', text: t});
            }
        }

        // 3. Look for elements with font-weight bolder near the top
        const allTextElements = Array.from(document.querySelectorAll('b, span, div, font, h1, h2, h3'));
        for (const el of allTextElements) {
            const style = window.getComputedStyle(el);
            if (style.fontWeight === 'bold' || style.fontWeight >= 700 || el.tagName === 'B') {
                if (el.innerText) {
                    let t = el.innerText.trim();
                    if (t.length > 2 && t.length < 100 && !ignoreList.some(i => t.includes(i))) {
                        possibleTitles.push({source: 'bold-text', text: t});
                    }
                }
            }
        }

        return possibleTitles;
    }''')
    
    print("EXTRACTED TITLES:")
    from pprint import pprint
    pprint(val)
    
    await b.close()
    await p.stop()

asyncio.run(run())
