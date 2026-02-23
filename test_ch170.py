import asyncio
from playwright.async_api import async_playwright

async def run():
    p = await async_playwright().start()
    context = await p.chromium.launch_persistent_context(
        user_data_dir=r'C:\Users\admin\Documents\Projects\novelpia\output\temp_profile',
        executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', 
        headless=True
    )
    page = await context.new_page()
    
    print("Navigating to chapter 170 (Next one after 169 - 8723)...")
    try:
        # Avoid domcontentloaded wait which often stalls, just commit the navigation
        res1 = await page.goto('https://global.novelpia.com/viewer/8723', wait_until="commit", timeout=60000)
        print(f"Commit Status: {res1.status}")
        await page.wait_for_timeout(5000)
    except Exception as e:
        print(f"Navigation exception: {e}")
        
    try:
        title = await page.title()
        print(f"Title: {title}")
        
        # Check if next button exists at all
        next_btn = await page.query_selector('.next-epi-btn')
        if not next_btn:
            print("Next button DOES NOT EXIST on this page.")
        else:
            class_attr = await next_btn.get_attribute("class") or ""
            print(f"Next btn classes on 169: {class_attr}")
            
            if "disabled" in class_attr:
                print("BUTTON IS DISABLED. End of chapters?")
            else:
                print("Clicking next...")
                await next_btn.click()
                await page.wait_for_timeout(3000)
                
                print(f"Landed on: {page.url}")
                title = await page.title()
                print(f"Title: {title}")
                
    except Exception as e:
        print(f"Evaluation exception: {e}")

    await context.close()
    await p.stop()

asyncio.run(run())
