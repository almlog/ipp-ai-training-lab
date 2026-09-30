import pytest
from app.agent import (
    HitmanState,
    MODE_TRAINING,
    TRAINING_LEVEL_STANDARD,
    TRAINING_LEVEL_ADVANCE,
    TRAINING_LEVEL_PROFESSIONAL,
    SEQUENCE_STANDARD,
    SEQUENCE_ADVANCE,
    SEQUENCE_PROFESSIONAL,
    set_training_level,
    get_training_sop,
    judge_ui_audit_output,
    get_step_verification_kind,
    verify_step_output,
)


class DummySession:
    def __init__(self, state_dict):
        self.state = state_dict


class DummyContext:
    def __init__(self, hitman_state):
        self.state = hitman_state._s
        self.session = DummySession(hitman_state._s)


def test_level_sequence_lengths():
    """各レベルのステップ数が 6 / 8 / 10 であることの確認"""
    assert len(SEQUENCE_STANDARD) == 6
    assert len(SEQUENCE_ADVANCE) == 8
    assert len(SEQUENCE_PROFESSIONAL) == 10
    assert SEQUENCE_STANDARD == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6"]
    assert SEQUENCE_ADVANCE == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6", "T-7", "T-8"]
    assert SEQUENCE_PROFESSIONAL == ["T-1", "T-2", "T-3", "T-4", "T-5", "T-6", "T-7", "T-8", "T-9", "T-10"]


def test_set_training_level():
    """レベル設定API・関数のステート反映テスト"""
    state = HitmanState({})
    state.mode = MODE_TRAINING
    state.course = "original"
    state.level = TRAINING_LEVEL_STANDARD

    ctx = DummyContext(state)
    res = set_training_level("advance", tool_context=ctx)
    assert res["level"] == "advance"
    assert res["step_sequence"] == SEQUENCE_ADVANCE
    assert state.level == "advance"

    res_pro = set_training_level("professional", tool_context=ctx)
    assert res_pro["level"] == "professional"
    assert res_pro["step_sequence"] == SEQUENCE_PROFESSIONAL
    assert state.level == "professional"


def test_training_sop_generation_per_level():
    """企画書確定後の各レベルの SOP 生成検証"""
    brief = {
        "display_name": "備品貸出アシスタント",
        "agent_name": "equipment_lending_agent",
        "features": [{"id": "F1", "name": "貸出登録"}],
        "screens": [{"id": "S1", "name": "貸出一覧"}],
        "tools": [{"name": "lend_item"}],
        "data": [{"name": "貸出記録"}],
        "out_of_scope": ["ログイン機能"],
        "q1": "明日プロジェクターは空いてる？",
        "q2": "PCを貸し出して",
    }

    # Lv.1: Standard (6 steps)
    state_std = HitmanState({})
    state_std.mode = MODE_TRAINING
    state_std.course = "original"
    state_std.level = TRAINING_LEVEL_STANDARD
    state_std.brief = brief
    sop_std = get_training_sop("original", state=state_std)
    assert "T-6" in sop_std
    assert "T-7" not in sop_std

    # Lv.2: Advance (8 steps)
    state_adv = HitmanState({})
    state_adv.mode = MODE_TRAINING
    state_adv.course = "original"
    state_adv.level = TRAINING_LEVEL_ADVANCE
    state_adv.brief = brief
    sop_adv = get_training_sop("original", state=state_adv)
    assert "T-4" in sop_adv and "Google標準リッチUI" in sop_adv["T-4"]["title"]
    assert "T-7" in sop_adv and "Cloud Run" in sop_adv["T-7"]["title"]
    assert "T-8" in sop_adv and "個人GitHub" in sop_adv["T-8"]["title"]

    # Lv.3: Professional (10 steps)
    state_pro = HitmanState({})
    state_pro.mode = MODE_TRAINING
    state_pro.course = "original"
    state_pro.level = TRAINING_LEVEL_PROFESSIONAL
    state_pro.brief = brief
    sop_pro = get_training_sop("original", state=state_pro)
    assert "T-4" in sop_pro and "Google標準リッチUI" in sop_pro["T-4"]["title"]
    assert "T-5" in sop_pro and "store.py" in sop_pro["T-5"]["title"]
    assert "T-9" in sop_pro and "セキュリティ" in sop_pro["T-9"]["title"]
    assert "T-10" in sop_pro and "最高位修了認定" in sop_pro["T-10"]["title"]


def test_ui_audit_output_judgement():
    """judge_ui_audit_output の合否判定テスト"""
    # 1. ログなし
    absent = judge_ui_audit_output("")
    assert absent["status"] == "ABSENT"

    # 2. 合格ログ (85点)
    pass_log = """
[skill:ipp-build-app-from-brief@v1]
# IPP AI研修: Google標準リッチUI 品質監査レポート
- **対象ファイル**: `ipp-agent-workspace/equipment_lending_agent/static/index.html`
- **品質スコア**: **85 / 100 点**
- **総合判定**: **UI_AUDIT: PASS ✓**

## 評価項目詳細
- **Google Fonts**: PASS (+20点) - Noto Sans JP
- **Material Symbols**: PASS (+20点) - material-symbols-outlined
- **Tailwind CSS / モダンCSS**: PASS (+25点) - Tailwind CDN
- **カード型UI**: PASS (+20点) - カード型コンポーネント検出

UI_AUDIT_RESULT: PASS
"""
    res_pass = judge_ui_audit_output(pass_log)
    assert res_pass["status"] == "PASS"
    assert res_pass["score"] == 85

    # 3. 不合格ログ (素のHTML 15点)
    fail_log = """
[skill:ipp-build-app-from-brief@v1]
# IPP AI研修: Google標準リッチUI 品質監査レポート
- **品質スコア**: **15 / 100 点**
- **総合判定**: **UI_AUDIT: FAIL ✗**

## ❌ 改善が必要な項目 (Google標準リッチUIへのブラッシュアップ)
- Google Fonts が検出されませんでした。
- Material Symbols アイコンが検出されませんでした。
- Tailwind CSS が検出されませんでした。

UI_AUDIT_RESULT: FAIL
"""
    res_fail = judge_ui_audit_output(fail_log)
    assert res_fail["status"] == "FAIL"
    assert res_fail["score"] == 15
    assert len(res_fail["hints"]) > 0


def test_step_verification_kinds():
    """レベルごとの検証種別マッピングの確認"""
    # Lv.1
    assert get_step_verification_kind("T-3", TRAINING_LEVEL_STANDARD) == "smoke"
    assert get_step_verification_kind("T-4", TRAINING_LEVEL_STANDARD) == "pytest"
    assert get_step_verification_kind("T-5", TRAINING_LEVEL_STANDARD) == "deploy"
    assert get_step_verification_kind("T-6", TRAINING_LEVEL_STANDARD) == "github"

    # Lv.2
    assert get_step_verification_kind("T-3", TRAINING_LEVEL_ADVANCE) == "smoke"
    assert get_step_verification_kind("T-4", TRAINING_LEVEL_ADVANCE) == "ui_audit"
    assert get_step_verification_kind("T-5", TRAINING_LEVEL_ADVANCE) == "pytest"
    assert get_step_verification_kind("T-6", TRAINING_LEVEL_ADVANCE) == "smoke"
    assert get_step_verification_kind("T-7", TRAINING_LEVEL_ADVANCE) == "deploy"
    assert get_step_verification_kind("T-8", TRAINING_LEVEL_ADVANCE) == "github"

    # Lv.3
    assert get_step_verification_kind("T-4", TRAINING_LEVEL_PROFESSIONAL) == "ui_audit"
    assert get_step_verification_kind("T-9", TRAINING_LEVEL_PROFESSIONAL) == "secret_scan"
    assert get_step_verification_kind("T-10", TRAINING_LEVEL_PROFESSIONAL) == "github"


def test_ui_audit_step_verification_gatekeeper():
    """Lv.2 T-4 における UI 監査ゲートキーパー動作検証（素のHTMLは差し戻し、リッチUIは承認）"""
    state_adv = HitmanState({})
    state_adv.mode = MODE_TRAINING
    state_adv.course = "original"
    state_adv.level = TRAINING_LEVEL_ADVANCE
    state_adv.current_step = "T-4"
    ctx = DummyContext(state_adv)

    # 素のHTMLの監査結果（FAIL）を投入 -> BLOCKED_RETRY で差し戻し
    fail_log = """
[skill:ipp-build-app-from-brief@v1]
# IPP AI研修: Google標準リッチUI 品質監査レポート
- **品質スコア**: **15 / 100 点**
UI_AUDIT_RESULT: FAIL
"""
    v_fail = verify_step_output("T-4", fail_log, tool_context=ctx)
    assert v_fail["verdict"] == "FAILED"
    assert v_fail["w_check_status"] == "BLOCKED_RETRY"
    assert "80点以上" in v_fail["reason"] or "品質スコア" in v_fail["reason"]

    # Google標準リッチUIの監査結果（PASS）を投入 -> VERIFIED_APPROVED で合格
    pass_log = """
[skill:ipp-build-app-from-brief@v1]
# IPP AI研修: Google標準リッチUI 品質監査レポート
- **品質スコア**: **95 / 100 点**
UI_AUDIT_RESULT: PASS
"""
    v_pass = verify_step_output("T-4", pass_log, tool_context=ctx)
    assert v_pass["verdict"] == "SUCCESS"
    assert v_pass["w_check_status"] == "VERIFIED_APPROVED"
    assert "ステップ T-5" in v_pass["message"]
