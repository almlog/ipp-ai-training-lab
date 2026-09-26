import asyncio
from playwright.async_api import async_playwright

async def wait_until_ready(page, timeout=30000):
    # 送信ボタンが disabled でなくなり、かつ「検証中」インジケータが消えるまで待機
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout / 1000:
        await page.wait_for_timeout(1000)
        indicator = await page.query_selector(".loading-indicator, #status-spinner")
        is_submitting = await page.evaluate("() => window.isSubmitting || false")
        # フォームの送信ボタンが活性化しているか
        disabled = await page.evaluate("() => document.getElementById('send-btn')?.disabled || false")
        if not is_submitting and not disabled:
            # 安定化のため追加ウェイト
            await page.wait_for_timeout(2000)
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
        await page.wait_for_timeout(2000)
        
        # 3. T-1 の Windows PowerShell ログを投入して T-1 を合格させる
        win_log = (
            "PS C:\\Users\\suzuki\\ipp-agent-workspace> Get-ChildItem ipp-ai-training-lab\\.agents\\skills\\\n"
            "    Directory: C:\\Users\\suzuki\\ipp-agent-workspace\\ipp-ai-training-lab\\.agents\\skills\n\n"
            "Mode                 LastWriteTime         Length Name\n"
            "----                 -------------         ------ ----\n"
            "d----          2026/09/24     19:00                pick-your-agent-project\n"
            "d----          2026/09/24     19:00                enable-a2ui\n"
            "d----          2026/09/24     19:00                build-agent-frontend\n"
        )
        chat_input = page.locator("#input")
        await chat_input.fill(win_log)
        await page.locator("#send-btn").click()
        print("T-1 log sent, waiting for verification...")
        await wait_until_ready(page)
        
        # T-1 合格後のスクリーンショット
        await page.screenshot(path=r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_t1_passed_flow.png", full_page=True)
        print("T-1 pass screenshot taken.")
        
        # 4. T-2 アイデア相談を投入
        await chat_input.fill("カレンダーとガントチャートが連動した予定管理ツールを作りたいのですが、作れますか？")
        await page.locator("#send-btn").click()
        print("T-2 idea sent, waiting for response...")
        await wait_until_ready(page)
        
        # T-2 アイデア相談後のスクリーンショット
        await page.screenshot(path=r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_t2_consulting_flow.png", full_page=True)
        print("T-2 consulting screenshot taken.")
        
        # 5. 「これで決定！」を投入
        await chat_input.fill("これで決定！")
        await page.locator("#send-btn").click()
        print("T-2 confirm sent, waiting for response...")
        await wait_until_ready(page)
        
        # T-2 確定後のスクリーンショット
        await page.screenshot(path=r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_t2_confirmed_final.png", full_page=True)
        print("T-2 confirmed screenshot taken.")
        
        await browser.close()

asyncio.run(run())
