import asyncio
from playwright.async_api import async_playwright

async def wait_until_ready(page, timeout=40000):
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout / 1000:
        await page.wait_for_timeout(1000)
        disabled = await page.evaluate("() => document.getElementById('send-btn')?.disabled || false")
        if not disabled:
            await page.wait_for_timeout(1000)
            return
    print("Wait timeout reached, proceeding...")

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        # 1. ページロード
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(2000)
        
        # 2. 研修モードへ切り替え
        mode_select = page.locator("#mode-select-hdr")
        await mode_select.select_option("TRAINING")
        await wait_until_ready(page)
        
        # 3. ユーザーのアイデアを相談
        chat_input = page.locator("#input")
        await chat_input.fill("カレンダー＆WBS形式のスケジュール管理とプライバシー保護機能を備えたAIツールを作りたい")
        send_btn = page.locator("#send-btn")
        await send_btn.click()
        print("Consulting idea sent...")
        await wait_until_ready(page)
        
        # 4. 「これで決定！このアイデアで進めます。」を送信
        await chat_input.fill("これで決定！このアイデアで進めます。")
        await send_btn.click()
        print("Confirm message sent...")
        await wait_until_ready(page)
        
        # 5. 最新のチャットバブルとカードの検証 (#log)
        chat_log = await page.locator("#log").inner_text()
        
        # 確定メッセージの検証
        assert "project_brief.md" in chat_log, "project_brief.md がチャット内に提示されていません"
        assert "hitman_spec.md" not in chat_log, "コースBの hitman_spec.md がチャットに誤って提示されています！"
        assert "コースA" in chat_log or "オリジナル" in chat_log, "コースAが確定されていません"
        print("SUCCESS! Course A was perfectly retained with custom idea and project_brief.md was issued!")
        
        # 画面キャプチャ保存
        shot_path = r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_custom_idea_confirmed_success.png"
        await page.screenshot(path=shot_path, full_page=True)
        print(f"Confirmed screenshot saved to {shot_path}")
        
        await browser.close()

asyncio.run(run())
