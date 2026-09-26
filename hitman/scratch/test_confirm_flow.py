import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        # 1. ページロード
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(1500)
        
        # 2. 研修モードへ切り替え
        mode_select = page.locator("#mode-select-hdr")
        await mode_select.select_option("TRAINING")
        await page.wait_for_timeout(2000)
        
        # 3. チャット欄に「これで決定！」を入力して送信
        chat_input = page.locator("#input")
        await chat_input.fill("これで決定！")
        send_btn = page.locator("#send-btn")
        await send_btn.click()
        
        # レスポンスが完了するまで待機
        print("Waiting for confirm response...")
        await page.wait_for_timeout(15000)
        
        # 4. スクリーンショット撮影
        shot_path = r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_t2_confirmed_live.png"
        await page.screenshot(path=shot_path, full_page=True)
        print(f"Screenshot saved to {shot_path}")
        
        await browser.close()

asyncio.run(run())
