"""
Unit Tests for HITMAN Lite Agent
自律Wチェック判定エンジン（自己申告遮断、エラー検知、正常合格）の検証
"""

import pytest
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import verify_step_output, get_sop_step_info, root_agent
from excel_parser import parse_sop_file

def test_pure_claim_blocked():
    """自己申告（'完了しました'等）のみの入力が正しく差し戻されることをテスト"""
    claim_inputs = [
        "完了しました",
        "無事に成功しました！",
        "問題ありませんでした",
        "ステップ実行しました",
    ]
    for inp in claim_inputs:
        res = verify_step_output("1-1", inp)
        assert res["verdict"] == "REJECT", f"Expected REJECT for '{inp}', got {res['verdict']}"
        assert res["w_check_status"] == "CLAIM_BLOCKED"

def test_error_detection_and_escalation():
    """ターミナルログ内のエラーを検知してエスカレーションゲートへ誘導することをテスト"""
    error_inputs = [
        "Command 'git pull' failed with exit code 1. error: cannot open file",
        "Exception in thread 'main': Connection timed out",
        "Permission denied: /var/log/app.log",
    ]
    for inp in error_inputs:
        res = verify_step_output("2-1", inp)
        assert res["verdict"] == "ERROR", f"Expected ERROR for '{inp}', got {res['verdict']}"
        assert res["w_check_status"] == "ESCALATION_REQUIRED"

def test_valid_log_approved():
    """正常なコマンド実行生ログが合格承認（VERIFIED_APPROVED）されることをテスト"""
    valid_logs = [
        "$ df -h /\nFilesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        50G   15G   33G  32% /",
        "$ pg_isready -h db.production.local\ndb.production.local:5432 - accepting connections",
        "$ curl -I http://localhost:8080/health\nHTTP/1.1 200 OK\nContent-Type: application/json",
    ]
    for log in valid_logs:
        res = verify_step_output("1-1", log)
        assert res["verdict"] == "SUCCESS", f"Expected SUCCESS for log, got {res['verdict']}"
        assert res["w_check_status"] == "VERIFIED_APPROVED"

def test_sop_parser_and_root_agent():
    """手順書パーサーおよびADK Agentの設定をテスト"""
    sop = parse_sop_file("")
    assert "1-1" in sop
    assert "4-1" in sop
    assert sop["1-1"]["command"] == "df -h /"

    assert root_agent.name == "hitman_lite"
    assert len(root_agent.tools) >= 2
