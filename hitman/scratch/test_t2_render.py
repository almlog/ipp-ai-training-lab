import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        # 1. ページロード
        await page.goto("http://localhost:3000/")
        await page.wait_for_timeout(2000)
        
        # 2. 研修モードに切り替え
        await page.evaluate("""
            async () => {
                await fetch('/api/mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: 'TRAINING'})
                });
                await fetch('/api/training/course', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({course: 'original'})
                });
                // ガイダンス（T-2 相談）を呼ぶ
                const res = await fetch('/api/training/guidance', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        idea: 'カレンダーとガントチャートが連動した予定管理ツール',
                        course_type: 'custom',
                        is_confirmed: false
                    })
                });
                const data = await res.json();
                
                // カードを描画
                if (window.renderTrainingStepCard) {
                    window.renderTrainingStepCard(data);
                } else if (window.renderA2uiMessage) {
                    window.renderA2uiMessage(data);
                }
                if (window.loadSopList) {
                    await window.loadSopList();
                }
            }
        """)
        await page.wait_for_timeout(2000)
        
        # 3. スクリーンショット撮影
        shot_path = r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39\shot_user_t2_fixed_test.png"
        await page.screenshot(path=shot_path, full_page=True)
        print(f"Screenshot saved to {shot_path}")
        
        await browser.close()

asyncio.run(run())
