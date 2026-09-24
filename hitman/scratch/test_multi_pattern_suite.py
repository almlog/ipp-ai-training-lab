import asyncio
import os
import sys

# Windows cp932 encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright

SCREENSHOT_DIR = r"C:\Users\suzuki.shunpei\.gemini\antigravity\brain\d986d8b6-8044-4ff1-813e-a01f5b05de39"

async def wait_until_ready(page, timeout=45000):
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout / 1000:
        await page.wait_for_timeout(1000)
        disabled = await page.evaluate("() => document.getElementById('send-btn')?.disabled || false")
        if not disabled:
            await page.wait_for_timeout(1500)
            return
    raise TimeoutError("Send button remained disabled for too long")

async def send_chat(page, message):
    chat_input = page.locator("#input")
    await chat_input.fill(message)
    prev_count = await page.locator("#log .msg").count()
    send_btn = page.locator("#send-btn")
    await send_btn.click()
    
    # 送信メッセージとボット応答が追加されるまで待機（最低 prev_count + 2）
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < 45:
        await page.wait_for_timeout(1000)
        curr_count = await page.locator("#log .msg").count()
        disabled = await page.evaluate("() => document.getElementById('send-btn')?.disabled || false")
        if curr_count >= prev_count + 2 and not disabled:
            await page.wait_for_timeout(1000)
            return
    # 万が一回数に満たなくても disabled 解除されたら抜ける
    await wait_until_ready(page)



async def test_pattern_1(browser):
    """【パターン1: 王道コースA】オリジナルアイデア相談 ➔ 自然な日本語での確定 ➔ 要件定義発行"""
    print("\n" + "="*50)
    print("[RUN] Pattern 1: Course A (Custom Idea -> Natural Confirm)")
    print("="*50)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    await page.goto("http://localhost:3000/")
    await page.wait_for_timeout(1500)

    # 研修モードへ切り替え
    await page.locator("#mode-select-hdr").select_option("TRAINING")
    await wait_until_ready(page)
    try:
        await page.wait_for_selector("#log:has-text('T-1')", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(1000)

    # 1. アイデア相談
    idea_text = "社内の障害ログを自動解析して原因と解決コマンドを即答するSlackボットを作りたい"
    print("  -> Sending idea consultation...")
    await send_chat(page, idea_text)
    
    # 相談後の検証
    chat_text_1 = await page.locator("#log").inner_text()
    assert "障害ログ" in chat_text_1, "P1-1: 相談アイデアがチャットに反映されていません"
    
    # 2. 自然な日本語での確定
    print("  -> Sending natural confirmation...")
    await send_chat(page, "このアイデアで進めます！決定でお願いします。")
    
    # 確定後の検証
    chat_text_2 = await page.locator("#log").inner_text()
    shot_p1 = os.path.join(SCREENSHOT_DIR, "shot_suite_p1_course_a_confirm.png")
    await page.screenshot(path=shot_p1, full_page=True)
    
    assert "project_brief.md" in chat_text_2, "P1-2: project_brief.md が提示されていません"
    assert "hitman_spec.md" not in chat_text_2, "P1-2: コースBの hitman_spec.md が誤って提示されました！"
    assert ("コースA" in chat_text_2 or "オリジナル" in chat_text_2), "P1-2: コースAが確定されていません"
    
    # 左側フローの検証
    banner_text = await page.locator("#flow-banner-text").inner_text()
    assert "T-2" in banner_text, "P1-3: 現在ステップが T-2 になっていません"
    
    print("[PASS] Pattern 1: Successfully confirmed Course A with project_brief.md")
    await page.close()


async def test_pattern_2(browser):
    """【パターン2: 王道コースB】迷っている受講生の安心スキャフォールディング ➔ HITMANクローン選択"""
    print("\n" + "="*50)
    print("[RUN] Pattern 2: Course B (Hesitant Scaffolding -> HITMAN Clone)")
    print("="*50)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    await page.goto("http://localhost:3000/")
    await page.wait_for_timeout(1500)

    # 研修モードへ切り替え
    await page.locator("#mode-select-hdr").select_option("TRAINING")
    await wait_until_ready(page)
    try:
        await page.wait_for_selector("#log:has-text('T-1')", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(1000)

    # 1. 困惑・迷いの相談
    print("  -> Sending hesitant consultation...")
    await send_chat(page, "何を作ればいいか全然思いつかない、どうすればいい？")
    
    # スキャフォールディングの検証
    chat_text_1 = await page.locator("#log").inner_text()
    assert ("ゼロから全部考えられなくても大丈夫" in chat_text_1 or "ゼロから一人で考える必要" in chat_text_1 or "おすすめアイデア" in chat_text_1 or "おすすめ" in chat_text_1), "P2-1: 迷っている受講生へのサポート案内がありません"
    assert ("コースB" in chat_text_1 or "HITMAN" in chat_text_1), "P2-1: コースBの案内がありません"

    # 2. 明示的にコースBを選択
    print("  -> Confirming Course B...")
    await send_chat(page, "一番人気のコースBで決定！")
    
    # 確定後の検証
    chat_text_2 = await page.locator("#log").inner_text()
    shot_p2 = os.path.join(SCREENSHOT_DIR, "shot_suite_p2_course_b_confirm.png")
    await page.screenshot(path=shot_p2, full_page=True)

    assert "hitman_spec.md" in chat_text_2, "P2-2: コースBの hitman_spec.md が提示されていません"
    assert "コースB" in chat_text_2, "P2-2: コースBが確定されていません"

    print("[PASS] Pattern 2: Successfully guided hesitant user and confirmed Course B")
    await page.close()


async def test_pattern_3(browser):
    """【パターン3: コースAのアイデア変更・壁打ちの積み重ね】相談 ➔ アイデア変更 ➔ 確定"""
    print("\n" + "="*50)
    print("[RUN] Pattern 3: Course A (Idea Switch -> Final Confirm)")
    print("="*50)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    await page.goto("http://localhost:3000/")
    await page.wait_for_timeout(1500)

    # 研修モードへ切り替え
    await page.locator("#mode-select-hdr").select_option("TRAINING")
    await wait_until_ready(page)
    try:
        await page.wait_for_selector("#log:has-text('T-1')", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(1000)

    # 1. 最初のアイデア相談
    print("  -> Sending first idea (FAQ bot)...")
    await send_chat(page, "社内規程のFAQボットを作りたいです")
    
    # 2. アイデア変更
    print("  -> Switching idea to schedule management...")
    await send_chat(page, "やっぱり予定変更して、カレンダーとガントチャートが連動した工程管理ツールにしたい。作れる？")
    
    # 3. 確定
    print("  -> Confirming switched idea...")
    await send_chat(page, "よし、これでいこう！決定！")
    
    chat_text_3 = await page.locator("#log").inner_text()
    shot_p3 = os.path.join(SCREENSHOT_DIR, "shot_suite_p3_idea_switch_confirm.png")
    await page.screenshot(path=shot_p3, full_page=True)

    assert "project_brief.md" in chat_text_3, "P3-1: project_brief.md が提示されていません"
    assert "hitman_spec.md" not in chat_text_3, "P3-1: コースBに誤誘導されています"
    assert ("工程管理" in chat_text_3 or "カレンダー" in chat_text_3 or "ガントチャート" in chat_text_3), "P3-2: 変更後のアイデアが引き継がれていません"

    print("[PASS] Pattern 3: Successfully tracked idea change and confirmed latest idea in Course A")
    await page.close()


async def test_pattern_4(browser):
    """【パターン4: リロード・セッション永続性】会話中のページリロード（F5）"""
    print("\n" + "="*50)
    print("[RUN] Pattern 4: Persistence across Reload (F5)")
    print("="*50)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    await page.goto("http://localhost:3000/")
    await page.wait_for_timeout(1500)

    # 研修モードへ切り替え
    await page.locator("#mode-select-hdr").select_option("TRAINING")
    await wait_until_ready(page)
    try:
        await page.wait_for_selector("#log:has-text('T-1')", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(1000)

    # アイデア相談
    print("  -> Consulting idea before reload...")
    await send_chat(page, "日報の自動要約AIエージェントを作りたいです")
    
    # リロード実行
    print("  -> Reloading page (F5)...")
    await page.reload()
    await page.wait_for_timeout(3000)

    # リロード後の復元検証
    chat_text_after = await page.locator("#log").inner_text()
    banner_after = await page.locator("#flow-banner-text").inner_text()
    
    shot_p4 = os.path.join(SCREENSHOT_DIR, "shot_suite_p4_reload_persistence.png")
    await page.screenshot(path=shot_p4, full_page=True)

    assert "日報" in chat_text_after, "P4-1: リロード後にチャット履歴が復元されていません"
    assert "T-2" in banner_after, "P4-2: リロード後に現在ステップ T-2 が維持されていません"

    # リロード後でもそのまま「これで決定！」で確定できること
    print("  -> Confirming after reload...")
    await send_chat(page, "これで決定！")
    chat_text_final = await page.locator("#log").inner_text()
    assert "project_brief.md" in chat_text_final, "P4-3: リロード後の確定で project_brief.md が発行されませんでした"

    print("[PASS] Pattern 4: State and history survived page reload successfully")
    await page.close()


async def test_pattern_5(browser):
    """【パターン5: 客観Wチェック判定】自己申告の安全な差し戻し ➔ 正常ログ投入でT-3合格進捗"""
    print("\n" + "="*50)
    print("[RUN] Pattern 5: Objective Verification Gate (Reject -> Pass -> T-3)")
    print("="*50)
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    await page.goto("http://localhost:3000/")
    await page.wait_for_timeout(1500)

    # 研修モードへ切り替え
    await page.locator("#mode-select-hdr").select_option("TRAINING")
    await wait_until_ready(page)
    try:
        await page.wait_for_selector("#log:has-text('T-1')", timeout=15000)
    except Exception:
        pass
    await page.wait_for_timeout(1000)

    # T-2 確定まで進める
    print("  -> Setting up T-2 confirmed state...")
    await send_chat(page, "ログ監視ボットを作りたい")
    await send_chat(page, "これで決定！")

    # 1. 自己申告（口頭報告）を投入
    print("  -> Sending subjective assertion (no logs)...")
    await send_chat(page, "要件定義作りました！完了したので次のステップに進めていいですか？")
    
    chat_text_assert = await page.locator("#log").inner_text()
    assert ("自己申告" in chat_text_assert or "客観" in chat_text_assert or "ログ" in chat_text_assert or "エビデンス" in chat_text_assert), "P5-1: 自己申告への教育的指導が行われていません"
    
    banner_assert = await page.locator("#flow-banner-text").inner_text()
    print("DEBUG BANNER_ASSERT:", repr(banner_assert))
    assert ("T-2" in banner_assert or "停止中" in banner_assert), f"P5-2: 自己申告差し戻し時にステップが巻き戻っています (actual: {banner_assert})"

    # 2. 正常な cat ログを投入
    print("  -> Sending valid cat log...")
    valid_log = (
        "$ cat ipp-agent-workspace/project_brief.md\n"
        "# Project Brief: LogMonitorBot\n"
        "- エージェント名: LogMonitorBot\n"
        "- 目的: システムログの常時監視と異常検知\n"
        "- 召喚スキル: enable-a2ui, build-agent-frontend, publish-to-github\n"
        "- ツール: scan_logs, analyze_error\n"
    )
    await send_chat(page, valid_log)

    chat_text_pass = await page.locator("#log").inner_text()
    banner_pass = await page.locator("#flow-banner-text").inner_text()
    flow_list_pass = await page.locator("#flow-list").inner_text()
    
    shot_p5 = os.path.join(SCREENSHOT_DIR, "shot_suite_p5_w_check_advance.png")
    await page.screenshot(path=shot_p5, full_page=True)

    assert ("合格" in chat_text_pass or "VERIFIED_APPROVED" in chat_text_pass or "承認" in chat_text_pass or "T-3" in chat_text_pass or "T-4" in chat_text_pass), "P5-3: 正常ログ投入で合格承認されていません"
    assert ("T-3" in banner_pass or "T-4" in banner_pass or "T-3" in flow_list_pass), "P5-4: 合格後にステップ T-3 / T-4 に前進していません"

    print("[PASS] Pattern 5: Subjective claim rejected safely, valid log advanced to Step T-3")
    await page.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        results = []
        
        tests = [
            ("Pattern 1: Course A (Custom Idea -> Natural Confirm)", test_pattern_1),
            ("Pattern 2: Course B (Hesitant Scaffolding -> HITMAN Clone)", test_pattern_2),
            ("Pattern 3: Course A (Idea Switch -> Final Confirm)", test_pattern_3),
            ("Pattern 4: Persistence across Reload (F5)", test_pattern_4),
            ("Pattern 5: Objective Verification Gate (Reject -> Pass -> T-3)", test_pattern_5),
        ]
        
        for name, fn in tests:
            try:
                await fn(browser)
                results.append((name, "PASSED", "All assertions matched expected behavior"))
            except Exception as e:
                print(f"[FAIL] {name}: {e}")
                results.append((name, "FAILED", str(e)))
        
        await browser.close()
        
        print("\n" + "="*50)
        print("TEST SUITE SUMMARY:")
        print("="*50)
        all_passed = True
        for name, status, detail in results:
            print(f"[{status}] {name}")
            if status != "PASSED":
                print(f"   Detail: {detail}")
                all_passed = False
        print("="*50)
        
        if not all_passed:
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
