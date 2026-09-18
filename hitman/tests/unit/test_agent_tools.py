# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
# Developed by Shunpei Suzuki <suzuki.shunpei@ipp.local>
#
from app.agent import (
    ACTIVE_STEP_SEQUENCE,
    analyze_sql_impact,
    evaluate_escalation_gate,
    generate_final_report,
    get_active_sop,
    get_operation_mode,
    get_procedure_step,
    guide_training_app_creation,
    import_sop_procedure,
    request_supervisor_step_skip,
    reset_active_sop,
    set_operation_mode,
    set_training_course,
    verify_step_output,
)


def test_get_procedure_step_found():
    step1 = get_procedure_step(1)
    assert step1["status"] == "found"
    assert "バックアップ" in step1["title"]
    assert "tar" in step1["command"]


def test_get_procedure_step_not_found():
    invalid_step = get_procedure_step(999)
    assert invalid_step["status"] == "not_found"


def test_verify_step_output_success():
    result = verify_step_output(1, "tar: app_20260904.tar.gz created successfully.")
    assert result["verdict"] == "SUCCESS"


def test_verify_step_output_teraterm_log():
    raw_teraterm_log = """[2026-09-06 00:10:52.123] \x1b[?2004h[app-user@bastion ~]$ df -h /backup\x1b[0m\r
[2026-09-06 00:10:53.456] Filesystem\t\tSize\tUsed\tAvail\tUse%\tMounted on\r
[2026-09-06 00:10:53.457] /dev/mapper/vg-backup\t50G\t15G\t33G\t32%\t/backup\r
[2026-09-06 00:10:54.000] \x1b[?2004l[app-user@bastion ~]$ \x1b[0m"""
    result = verify_step_output("1-1", raw_teraterm_log)
    assert result["verdict"] == "SUCCESS"
    assert "空き容量が十分" in result["message"]


def test_verify_step_output_failure():
    result = verify_step_output(2, "Job for my-app.service failed because of error.")
    assert result["verdict"] == "FAILED"
    assert "エラーキーワード" in result["reason"]


def test_analyze_sql_impact_match():
    pre_select = """+-----+-----------+---------+----------+
| id  | tenant_id | status  | plan     |
+-----+-----------+---------+----------+
| 105 | T100      | PENDING | STANDARD |
+-----+-----------+---------+----------+
1 row in set (0.01 sec)"""
    sql = "UPDATE users SET status = 'ACTIVE', plan = 'ENTERPRISE' WHERE tenant_id = 'T100';"
    res = analyze_sql_impact("3-3", pre_select, sql)
    assert res["verdict"] == "MATCH"
    assert res["escalation_required"] is False
    assert "要件合致" in res["requirement_satisfaction"]


def test_analyze_sql_impact_dangerous_missing_where():
    pre_select = "1 row in set"
    sql = "UPDATE users SET status = 'ACTIVE';"
    res = analyze_sql_impact("3-3", pre_select, sql)
    assert res["verdict"] == "HIGH_RISK"
    assert res["escalation_required"] is True
    assert res["branch_to"] == "E-1"
    assert "WHERE" in res["reason"]


def test_analyze_sql_impact_mismatch_tenant():
    pre_select = "105 | T100 | PENDING"
    sql = "UPDATE users SET status = 'ACTIVE' WHERE tenant_id = 'T999';"
    res = analyze_sql_impact("3-3", pre_select, sql)
    assert res["verdict"] == "MISMATCH"
    assert res["escalation_required"] is True
    assert res["branch_to"] == "E-1"


def test_evaluate_escalation_gate_blocked_without_grounds():
    res = evaluate_escalation_gate(
        escalation_result="協議しました",
        decision="GO",
        grounds="",  # 空の根拠
    )
    assert res["status"] == "BLOCKED"
    assert res["allowed_to_proceed"] is False
    assert "根拠" in res["reason"]


def test_evaluate_escalation_gate_nogo():
    res = evaluate_escalation_gate(
        escalation_result="開発元と協議し、不整合が解消できないため作業中断を決定",
        decision="NOGO",
        grounds="データ破損リスクが高く、夜間メンテ枠での再作業に切り替えるため (承認: 運用責任者 田中)",
    )
    assert res["status"] == "NOGO"
    assert res["allowed_to_proceed"] is False
    assert res["branch_to"] == "R-1"


def test_evaluate_escalation_gate_go_normal():
    res = evaluate_escalation_gate(
        escalation_result="SQLファイルのWHERE句をT100に修正し、再レビュー完了",
        decision="GO",
        grounds="手順書仕様書v2.1の要件定義に完全一致することを確認 (Slack承認: #rel-deploy-105)",
        is_standard_procedure=True,
    )
    assert res["status"] == "GO_NORMAL"
    assert res["allowed_to_proceed"] is True
    assert res["mode"] == "NORMAL"


def test_evaluate_escalation_gate_go_special_pair():
    res = evaluate_escalation_gate(
        escalation_result="本番特例として上長立会いのもとパッチ適用を決定",
        decision="GO",
        grounds="システム統括部長特命承認（ID: APPR-9912）に基づき2人体制で即時反映",
        is_standard_procedure=False,
        supervisor_name="山田部長",
    )
    assert res["status"] == "GO_SPECIAL"
    assert res["allowed_to_proceed"] is True
    assert res["mode"] == "SPECIAL_PAIR"
    assert res["supervisor"] == "山田部長"


def test_evaluate_escalation_gate_go_special_leader_approval():
    # 「リーダー承認でいい」: supervisor_nameが空でも「作業リーダー（承認済）」を自動設定して進行許可
    res = evaluate_escalation_gate(
        escalation_result="作業リーダーと現場確認し特別対応の実施を合意",
        decision="GO",
        grounds="リーダー承認済、暫定パッチによる即時復旧方針",
        is_standard_procedure=False,
        supervisor_name="",
    )
    assert res["status"] == "GO_SPECIAL"
    assert res["allowed_to_proceed"] is True
    assert res["mode"] == "SPECIAL_PAIR"
    assert "作業リーダー" in res["supervisor"]


def test_step_sequence_definition():
    from app.agent import STEP_SEQUENCE
    assert STEP_SEQUENCE == [
        "1-1", "1-2", "2-1", "2-2", "3-1", "3-2", "3-3", "3-4", "4-1", "4-2"
    ]


def test_generate_final_report():
    report = generate_final_report(
        start_time="2026-09-06 00:00:00",
        end_time="2026-09-06 00:30:00",
        duration_minutes=30,
        mode="SPECIAL_PAIR",
        supervisor_name="山田部長",
    )
    assert "最終評価" in report["title"]
    assert report["work_duration"]["elapsed_minutes"] == 30
    assert report["operation_mode"]["two_person_rule_applied"] is True
    assert len(report["deliverables"]) >= 4


def test_consult_sop_knowledge():
    from app.agent import consult_sop_knowledge

    # 1. 正常系: ディスク容量不足の検索
    res = consult_sop_knowledge("バックアップ時のディスク空き容量不足について教えて")
    assert res["status"] == "found"
    assert "セクション1" in res["section_title"] or "ディスク" in res["section_title"]
    assert "df -h" in res["guidance"]

    # 2. 正常系: エスカレーション基準の検索
    res_esc = consult_sop_knowledge("エスカレーション基準やロールバック判断")
    assert res_esc["status"] == "found"
    assert "エスカレーション" in res_esc["section_title"]

    # 3. 該当なし
    res_none = consult_sop_knowledge("xyzxyz123456全く関係ないキーワード")
    assert res_none["status"] == "not_found"


def test_import_sop_procedure_markdown_table():
    reset_active_sop()
    md_content = """# PostgreSQL 定期メンテ手順書
| 項番 | 作業内容 | 投入コマンド | 期待ログ・判定基準 | 注意事項 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | DBヘルスチェック | pg_isready -h localhost -p 5432 | accepting connections | 接続不可時は即時連絡 |
| 2 | インデックス再構築 | REINDEX TABLE CONCURRENTLY users; | REINDEX | ピーク時実行厳禁 |
| 3 | 統計情報更新 | ANALYZE VERBOSE users; | ANALYZE | 負荷を監視 |
"""
    res = import_sop_procedure(md_content, format_type="markdown")
    assert res["status"] == "success"
    assert res["imported_steps_count"] >= 3
    assert any("1" in s for s in res["step_sequence"])

    # 検証: 新しい手順が取得できること
    step1 = get_procedure_step(1)
    assert step1["status"] == "found"
    assert "pg_isready" in step1["command"]
    assert "accepting connections" in step1["expected_check"]

    # 標準ロールバックとエスカレーションが安全のため維持されていること
    active_sop = get_active_sop()
    assert "R" in active_sop
    assert "E" in active_sop

    # クリーンアップ
    reset_active_sop()


def test_import_sop_procedure_tsv():
    reset_active_sop()
    tsv_content = (
        "項番\t作業内容\t実行コマンド\t期待結果\t注意事項\n"
        "1\tキャッシュクリア\tsystemctl restart redis\tActive: active\tデータ揮発確認\n"
        "2\tキュー監視\trq info\t0 failed\t滞留なし\n"
    )
    res = import_sop_procedure(tsv_content, format_type="tsv")
    assert res["status"] == "success"
    assert res["imported_steps_count"] >= 2
    step1 = get_procedure_step(1)
    assert "redis" in step1["command"]

    reset_active_sop()


def test_import_sop_procedure_json():
    reset_active_sop()
    import json
    steps_data = [
        {"id": "1", "title": "設定ファイル検証", "command": "nginx -t", "expected_output": "syntax is ok", "caution": "文法エラー時中断"},
        {"id": "2", "title": "リロード実行", "command": "systemctl reload nginx", "expected_output": "Active: active", "caution": "無停止リロード"}
    ]
    res = import_sop_procedure(json.dumps(steps_data), format_type="json")
    assert res["status"] == "success"
    assert res["imported_steps_count"] == 2
    step = get_procedure_step(1)
    assert "nginx -t" in step["command"]

    reset_active_sop()


def test_reset_active_sop():
    # カスタムSOPをインポートしてからリセット
    md_content = """| 項番 | 作業内容 | 投入コマンド | 期待結果 |
| 99 | 特別タスク | echo 'special' | special |"""
    import_sop_procedure(md_content, format_type="markdown")
    active_keys = [str(k) for k in get_active_sop().keys()]
    assert "99" in active_keys

    # リセット実行
    reset_res = reset_active_sop()
    assert isinstance(reset_res, dict)
    active_keys_after = [str(k) for k in reset_res.keys()]
    assert "99" not in active_keys_after
    assert "1" in active_keys_after
    assert "4" in active_keys_after


def test_verify_step_output_autonomous_verdicts():
    reset_active_sop()

    # 1. 承認合格: VERIFIED_APPROVED
    res_ok = verify_step_output("1-1", "Filesystem 50G 15G 33G 32% /backup")
    assert res_ok["verdict"] == "SUCCESS"
    assert res_ok["w_check_status"] == "VERIFIED_APPROVED"
    assert "Wチェック承認" in res_ok["autonomous_verdict"]

    # 2. 致命的エラーによる自律ロールバック判定: BRANCH_ROLLBACK
    res_fatal = verify_step_output("3-2", "Segmentation fault (core dumped) - fatal error occurred")
    assert res_fatal["verdict"] == "FAILED"
    assert res_fatal["w_check_status"] == "BRANCH_ROLLBACK"
    assert res_fatal["branch_to"] == "R-1"

    # 3. 競合・ロックによる自律エスカレーション判定: BRANCH_ESCALATION
    res_lock = verify_step_output("3-4", "ERROR 1205 (HY000): Lock wait timeout exceeded; deadlock detected")
    assert res_lock["verdict"] == "FAILED"
    assert res_lock["w_check_status"] == "BRANCH_ESCALATION"
    assert res_lock["branch_to"] == "E-1"

    # 4. ディスク容量枯渇・再実行ブロック: BLOCKED_RETRY
    res_retry = verify_step_output("1-1", "Filesystem 50G 50G 0G 100% /backup No space left on device")
    assert res_retry["verdict"] == "FAILED"
    assert res_retry["w_check_status"] == "BLOCKED_RETRY"


def test_frontend_api_sop_endpoints():
    from fastapi.testclient import TestClient
    from frontend.main import app
    client = TestClient(app)

    # 1. GET /api/sop
    res = client.get("/api/sop")
    assert res.status_code == 200
    data = res.json()
    assert "sop" in data
    assert "sequence" in data

    # 2. POST /api/sop/import
    md_content = """| 項番 | 作業内容 | 投入コマンド | 期待結果 |
| 1 | テスト手順 | echo test | test |"""
    res_import = client.post("/api/sop/import", json={"content": md_content, "format_type": "markdown"})
    assert res_import.status_code == 200
    import_data = res_import.json()
    assert import_data["result"]["status"] == "success"

    # 3. POST /api/sop/reset
    res_reset = client.post("/api/sop/reset")
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert "1" in [str(k) for k in reset_data["sop"].keys()]

    # 4. GET & POST /api/mode
    res_mode_get = client.get("/api/mode")
    assert res_mode_get.status_code == 200
    assert "mode" in res_mode_get.json()

    res_mode_set = client.post("/api/mode", json={"mode": "TRAINING"})
    assert res_mode_set.status_code == 200
    assert res_mode_set.json()["mode"] == "TRAINING"

    # Reset back to NORMAL
    client.post("/api/mode", json={"mode": "NORMAL"})

    # 5. POST /api/supervisor/skip
    res_skip = client.post("/api/supervisor/skip", json={
        "step_to_skip": "1-1",
        "supervisor_name": "山田 太郎",
        "supervisor_role": "統括部長",
        "skip_rationale": "夜間検証済みのため本手順は省略と上長判断",
        "user_responsibility_confirmed": True
    })
    assert res_skip.status_code == 200
    assert res_skip.json()["status"] == "APPROVED_SKIP"

    # 6. POST /api/training/guidance
    res_guide = client.post("/api/training/guidance", json={"idea": "DB自動監査ツール"})
    assert res_guide.status_code == 200
    assert "オリジナルアプリ開発コース" in res_guide.json()["course"]


def test_verify_step_output_rejects_pure_assertion():
    """自己申告メッセージ（ログ不在）が通常モードで確実に弾かれることを検証。"""
    set_operation_mode("NORMAL")
    user_assertion = "容量は空いてたよ。10GB以上ある。次のステップに進もう"
    result = verify_step_output("1-1", user_assertion)
    assert result["verdict"] == "FAILED"
    assert result["w_check_status"] == "REJECTED_NO_LOG"
    assert "自己申告のみ" in result["message"]

    # 他の自己申告文も確実に弾かれることを検証
    res_done = verify_step_output("1-2", "完了しました。次へ進めてください。")
    assert res_done["verdict"] == "FAILED"
    assert res_done["w_check_status"] == "REJECTED_NO_LOG"


def test_verify_step_output_training_mode_guidance():
    """研修モードでは自己申告に対して受講生に寄り添う教育的ガイダンスが返ることを検証。"""
    set_operation_mode("TRAINING")
    user_assertion = "大丈夫でした。問題ないです"
    result = verify_step_output("1-1", user_assertion)
    assert result["verdict"] == "FAILED"
    assert result["w_check_status"] == "TRAINING_GUIDANCE"
    assert "研修モード・教育ガイダンス" in result["message"]
    assert "客観的な証拠" in result["message"]
    assert "伴走" in result["message"] or "大変ですよね" in result["message"]
    # 通常モードに戻す
    set_operation_mode("NORMAL")


def test_verify_step_output_training_mode_maintains_current_step_on_assertion():
    """研修モードでステップ T-3 進行中に自己申告された際、T-1に巻き戻らずT-3のカード・ガイダンスが維持されることを検証。"""
    import app.agent as agent_module
    set_operation_mode("TRAINING")
    set_training_course("original")
    agent_module.CURRENT_STEP = "T-3"

    # ユーザーが「だいじょうぶそうだったよ。次のステップに進もう！」と自己申告
    # モデルが step_number="1" または "T-1" を誤って渡しても、CURRENT_STEP (T-3) が維持されること
    user_assertion = "だいじょうぶそうだったよ。次のステップに進もう！"
    result = verify_step_output("1-1", user_assertion)
    assert result["verdict"] == "FAILED"
    assert result["w_check_status"] == "TRAINING_GUIDANCE"
    assert result["step_id"] == "T-3"
    assert "ステップ T-3" in result["message"]
    assert "agent.py" in result["message"]

    # step_number="T-1" を渡した場合も T-3 が維持されること
    result_t1 = verify_step_output("T-1", user_assertion)
    assert result_t1["step_id"] == "T-3"

    # 通常モードに戻す
    set_operation_mode("NORMAL")


def test_supervisor_step_skip_tool():
    """上長責任による手順スキップツールの挙動検証（AI自発提案禁止・責任明文化）。"""
    # 1. 要件不足（理由なし） -> BLOCKED
    res_fail = request_supervisor_step_skip(
        step_to_skip="1-1",
        supervisor_name="山田 太郎",
        supervisor_role="運用統括部長",
        skip_rationale="",
        user_responsibility_confirmed=True,
    )
    assert res_fail["status"] == "BLOCKED"
    assert res_fail["allowed_to_proceed"] is False

    # 2. 責任受容未同意 -> BLOCKED
    res_no_resp = request_supervisor_step_skip(
        step_to_skip="1-1",
        supervisor_name="山田 太郎",
        supervisor_role="運用統括部長",
        skip_rationale="夜間自動バッチで既に別ディスクに容量確保済みのため本確認は不要",
        user_responsibility_confirmed=False,
    )
    assert res_no_resp["status"] == "BLOCKED"
    assert res_no_resp["allowed_to_proceed"] is False

    # 3. 全要件充足 -> APPROVED_SKIP
    res_ok = request_supervisor_step_skip(
        step_to_skip="1-1",
        supervisor_name="山田 太郎",
        supervisor_role="運用統括部長",
        skip_rationale="夜間自動バッチで既に別ディスクに容量確保済みのため本確認は不要と上長判断",
        user_responsibility_confirmed=True,
    )
    assert res_ok["status"] == "APPROVED_SKIP"
    assert res_ok["allowed_to_proceed"] is True
    assert res_ok["skipped_step"] == "1-1"
    assert "上長指示による例外スキップ承認" in res_ok["message"]


def test_guide_training_app_creation():
    """研修モードでのオリジナルアプリ開発またはHITMAN作成ガイダンスの検証。"""
    # 1. アイデアなし -> HITMAN作成コース（コースB）
    res_hitman = guide_training_app_creation("")
    assert res_hitman["status"] == "success"
    assert "HITMAN作成コース" in res_hitman["course"]
    assert "Excel手順書" in res_hitman["concept"]

    # 2. オリジナルアイデア -> カスタムアプリ開発コース（コースA）
    res_custom = guide_training_app_creation("社内Gitリポジトリのセキュリティ脆弱性自動監査エージェント")
    assert res_custom["status"] == "success"
    assert "オリジナルアプリ開発コース" in res_custom["course"]
    assert "Google ADK" in res_custom["recommended_architecture"]["framework"]

    # 3. 画像認識スキル召喚テスト（ルービックキューブ3面写真攻略）
    res_vision = guide_training_app_creation("ルービックキューブの写真を3面分共有するだけで、完全攻略のルートを表示させるAIアプリ")
    assert res_vision["status"] == "success"
    assert "gemini-multimodal-vision" in res_vision["summoned_skills"]
    assert "画像認識" in res_vision["prompt_for_antigravity"] or "写真" in res_vision["prompt_for_antigravity"]
    assert "enable-a2ui" in res_vision["summoned_skills"]

    # 4. RAGスキル召喚テスト（社内規程・マニュアル問い合わせBot）
    res_rag = guide_training_app_creation("社内就業規則やITセキュリティマニュアルの問い合わせ回答Bot")
    assert res_rag["status"] == "success"
    assert "build-rag" in res_rag["summoned_skills"]
    assert "RAG" in res_rag["prompt_for_antigravity"]

    # 5. 長期記憶スキル召喚テスト（ユーザーの好みを記憶するパーソナル推薦Bot）
    res_memory = guide_training_app_creation("会話履歴や過去のユーザー好みを記憶して個別最適な提案を行うエージェント")
    assert res_memory["status"] == "success"
    assert "setup-memory-bank" in res_memory["summoned_skills"]


def test_guide_training_app_creation_consultation_and_confirmation_gate():
    """ステップ T-2 のアイデア相談・壁打ちフェーズと確定ゲート制御の検証。"""
    # 1. 相談・壁打ちの質問（「え？自分で考えるの？そうだな、こういうアプリは作れるかな？」）
    # 受講生の戸惑いを受け止め、ゼロから考えなくてよい安心メッセージと3大定番が提示されること
    res_consult_1 = guide_training_app_creation("え？自分で考えるの？そうだな、こういうアプリは作れるかな？")
    assert res_consult_1["status"] == "success"
    assert res_consult_1["confirmation_status"] == "consulting"
    assert res_consult_1["is_confirmed"] is False
    assert res_consult_1["command"] == ""  # ターミナルコマンドを出さない
    assert "相談" in res_consult_1["title"] or "壁打ち" in res_consult_1["title"]
    assert "ゼロから全部考えられなくても大丈夫" in res_consult_1["message"]
    assert "障害ログ" in res_consult_1["message"]
    assert "コースB" in res_consult_1["message"]

    # 2. 完全な困惑（「思いつかない、何を入力すればいい？」）でも安心スキャフォールディングが返ること
    res_hesitant = guide_training_app_creation("思いつかない、何を入力すればいい？")
    assert res_hesitant["confirmation_status"] == "consulting"
    assert res_hesitant["is_confirmed"] is False
    assert res_hesitant["command"] == ""
    assert "ゼロから全部考えられなくても大丈夫" in res_hesitant["message"]
    assert "社内規程" in res_hesitant["message"] or "マニュアル" in res_hesitant["message"]

    # 3. 特定アイデアの実現性相談（「日報自動要約AIって作れる？」）
    res_consult_2 = guide_training_app_creation("日報自動要約AIって作れる？")
    assert res_consult_2["confirmation_status"] == "consulting"
    assert res_consult_2["command"] == ""
    assert "日報自動要約AI" in res_consult_2["user_idea"]
    assert "これで決定！" in res_consult_2["message"]

    # 4. 直前の相談アイデアを踏まえた確定（「これで決定！」）
    res_confirm = guide_training_app_creation("これで決定！")
    assert res_confirm["confirmation_status"] == "confirmed"
    assert res_confirm["is_confirmed"] is True
    assert res_confirm["command"] == "cat ipp-agent-workspace/project_brief.md"
    assert "コース確定" in res_confirm["message"]
    assert "日報自動要約AI" in res_confirm["user_idea"] or "日報自動要約AI" in res_confirm["title"]

    # 5. 明示的な is_confirmed フラグによる制御
    res_explicit_consult = guide_training_app_creation("障害ログ解析Bot", is_confirmed=False)
    assert res_explicit_consult["confirmation_status"] == "consulting"
    assert res_explicit_consult["command"] == ""

    res_explicit_confirm = guide_training_app_creation("障害ログ解析Bot", is_confirmed=True)
    assert res_explicit_confirm["confirmation_status"] == "confirmed"
    assert res_explicit_confirm["command"] == "cat ipp-agent-workspace/project_brief.md"

    # 6. コースB（HITMANクローン）の相談と確定
    res_hitman_consult = guide_training_app_creation("HITMANクローンってどういうもの？")
    assert res_hitman_consult["confirmation_status"] == "consulting"
    assert res_hitman_consult["command"] == ""
    assert "コースB" in res_hitman_consult["course"]
    assert "ゼロから全部考えられなくても大丈夫" in res_hitman_consult["message"]

    res_hitman_confirm = guide_training_app_creation("コースBで決定！")
    assert res_hitman_confirm["confirmation_status"] == "confirmed"
    assert res_hitman_confirm["command"] == "cat ipp-agent-workspace/hitman_spec.md"



def test_set_and_get_operation_mode():
    """運用モードの切り替えと情報取得の検証。"""
    # TRAINING
    set_operation_mode("TRAINING")
    info = get_operation_mode()
    assert info["mode"] == "TRAINING"
    assert "研修モード" in info["description"]

    # SPECIAL_PAIR
    set_operation_mode("SPECIAL_PAIR", supervisor_name="鈴木 駿平", supervisor_role="運用リード")
    info = get_operation_mode()
    assert info["mode"] == "SPECIAL_PAIR"
    assert info["supervisor_name"] == "鈴木 駿平"

    # NORMAL
    set_operation_mode("NORMAL")
    info = get_operation_mode()
    assert info["mode"] == "NORMAL"


def test_training_sop_and_course_switching():
    """研修モードでの受講コース切り替えおよびSOP動的取得の検証。"""
    from app.agent import (
        MODE_TRAINING,
        MODE_NORMAL,
        get_active_sop,
        get_active_step_sequence,
        get_active_approval,
        set_operation_mode,
        set_training_course,
    )

    # 1. 研修モードへ切り替え
    set_operation_mode(MODE_TRAINING)
    seq = get_active_step_sequence()
    assert seq == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]

    # 2. コースA (original) の確認
    res_orig = set_training_course("original")
    assert res_orig["status"] == "success"
    assert res_orig["course"] == "original"
    sop_orig = get_active_sop()
    assert "T-1" in sop_orig
    assert "T-6" in sop_orig
    assert "gemini-3.8-flash" in sop_orig["T-1"]["cautions"]
    assert "ipp-agent-workspace" in sop_orig["T-1"]["command"]

    appr_orig = get_active_approval()
    assert "コースA" in appr_orig["work_title"]

    # 3. コースB (hitman_clone) の確認
    res_clone = set_training_course("hitman_clone")
    assert res_clone["status"] == "success"
    assert res_clone["course"] == "hitman_clone"
    sop_clone = get_active_sop()
    assert "hitman_spec.md" in sop_clone["T-2"]["command"]
    assert "my_hitman" in sop_clone["T-3"]["command"]

    appr_clone = get_active_approval()
    assert "コースB" in appr_clone["work_title"]

    # 4. 通常モード復帰時は通常手順書に戻る
    set_operation_mode(MODE_NORMAL)
    seq_norm = get_active_step_sequence()
    assert seq_norm[0] == "1-1"


def test_training_step_verification_t1_to_t6():
    """研修ステップ T-1 〜 T-6 の客観ログ検証と合否判定の検証。"""
    from app.agent import verify_step_output

    # T-1: 正常合格 vs 自己申告差し戻し
    t1_pass = verify_step_output("T-1", "mkdir ipp-agent-workspace\ngit clone https://github.com/almlog/ipp-ai-training-lab.git\nCloning into 'ipp-ai-training-lab'...")
    assert t1_pass["verdict"] == "SUCCESS"
    assert t1_pass["w_check_status"] == "VERIFIED_APPROVED"

    t1_fail = verify_step_output("T-1", "環境構築完了しました！次はどうすればいいですか？")
    assert t1_fail["verdict"] == "FAILED"

    # T-2: Project Brief出力 vs ログ不在
    t2_pass = verify_step_output("T-2", "# Project Brief\n- エージェント名: AutoOpsAgent\n- 目的: 現場ログ監視と異常検知\n- ツール: log_analyzer, a2ui_card")
    assert t2_pass["verdict"] == "SUCCESS"

    t2_fail = verify_step_output("T-2", "要件定義作りました。進めていいですか？")
    assert t2_fail["verdict"] == "FAILED"

    # T-3: エージェント実装 vs ログ不在
    t3_pass = verify_step_output("T-3", "agent.py created\nimport google.adk\nroot_agent = Agent(name='my_agent')")
    assert t3_pass["verdict"] == "SUCCESS"

    # T-4: 単体テスト全件PASSED vs FAILED検知
    t4_pass = verify_step_output("T-4", "==================== 5 passed in 0.18s ====================")
    assert t4_pass["verdict"] == "SUCCESS"

    t4_fail = verify_step_output("T-4", "FAILED tests/test_agent.py::test_tools - AssertionError: 500 != 200\n1 failed, 4 passed in 0.20s")
    assert t4_fail["verdict"] == "FAILED"
    assert t4_fail["w_check_status"] == "BLOCKED_RETRY"

    # T-5: Cloud Run デプロイ成功
    t5_pass = verify_step_output("T-5", "Deploying container to Cloud Run service [my-agent]...\nService URL: https://my-agent-xyz-an.a.run.app\nDone.")
    assert t5_pass["verdict"] == "SUCCESS"

    # T-6: 個人GitHub公開・修了
    t6_pass = verify_step_output("T-6", "Enumerating objects: 42, done.\nTo https://github.com/suzuki-shunpei/my-agent.git\n * [new branch]      main -> main")
    assert t6_pass["verdict"] == "SUCCESS"
    assert "修了承認" in t6_pass["autonomous_verdict"]


def test_frontend_training_course_endpoints():
    """フロントエンドAPIプロキシでの研修モード・コース切り替えエンドポイントの検証。"""
    from fastapi.testclient import TestClient
    from frontend.main import app
    client = TestClient(app)

    # 1. GET /api/sop?mode=TRAINING&course=original
    res_orig = client.get("/api/sop?mode=TRAINING&course=original")
    assert res_orig.status_code == 200
    data_orig = res_orig.json()
    assert data_orig["sequence"] == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]
    assert "T-1" in data_orig["sop"]
    assert "コースA" in data_orig["approval"]["work_title"]

    # 2. GET /api/sop?mode=TRAINING&course=hitman_clone
    res_clone = client.get("/api/sop?mode=TRAINING&course=hitman_clone")
    assert res_clone.status_code == 200
    data_clone = res_clone.json()
    assert "コースB" in data_clone["approval"]["work_title"]

    # 3. POST /api/training/course
    res_post_course = client.post("/api/training/course", json={"course": "hitman_clone"})
    assert res_post_course.status_code == 200
    post_data = res_post_course.json()
    assert post_data["course"] == "hitman_clone"
    assert "T-1" in post_data["sop"]

    # 4. POST /api/training/parameters (Custom Workspace & Env)
    res_params = client.post("/api/training/parameters", json={
        "workspace_dir": "C:\\custom\\agent_ws",
        "agent_name": "custom_agent",
        "python_env": "conda_env"
    })
    assert res_params.status_code == 200
    param_data = res_params.json()
    assert param_data["status"] == "success"
    assert param_data["parameters"]["WORKSPACE_DIR"] == "C:\\custom\\agent_ws"

    # 5. GET /api/sop with custom parameters
    res_custom_sop = client.get("/api/sop?mode=TRAINING&course=original&workspace=C:\\custom\\agent_ws&agent=custom_agent")
    assert res_custom_sop.status_code == 200
    custom_sop_data = res_custom_sop.json()
    assert "C:\\custom\\agent_ws" in custom_sop_data["sop"]["T-1"]["command"]
    assert "custom_agent" in custom_sop_data["sop"]["T-3"]["command"]








