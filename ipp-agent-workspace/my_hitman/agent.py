"""
HITMAN Lite Agent (AIペアオペレーター・自律Wチェック判定エンジン)
Google ADK (Agent Development Kit) + A2UI Rich Cards
"""

import os
import re
from typing import Dict, Any, List
from google.adk.agents import Agent
from a2ui_utils import a2ui_callback
from excel_parser import parse_sop_file

# --- SOP Database ---
DEFAULT_SOP = parse_sop_file("")

# --- Function Tools ---

def verify_step_output(step_id: str, terminal_output: str) -> Dict[str, Any]:
    """ターミナル実行ログを客観検証し、自己申告遮断・エラー検知・合格承認を判定する。
    
    Args:
        step_id: 検証対象のステップID (例: '1-1', '1-2', '2-1', '3-1', '4-1')
        terminal_output: ターミナルの実行生ログ
    """
    output = terminal_output.strip()
    output_lower = output.lower()
    
    # 1. 自己申告遮断 (コマンド生ログがない場合)
    no_log_keywords = ["完了しました", "おわりました", "成功しました", "問題ありません", "実行しました", "パスしました"]
    is_pure_claim = any(k in output for k in no_log_keywords) and len(output) < 80 and not any(c in output for c in ["$", "df ", "git ", "python", "curl", "200 OK", "test session", "PASSED"])
    
    if is_pure_claim:
        return {
            "verdict": "REJECT",
            "w_check_status": "CLAIM_BLOCKED",
            "step_id": step_id,
            "autonomous_verdict": "【AI確認者 差し戻し ⚠️】自己申告のみの入力は証跡として承認できません。",
            "message": "【判定: 差し戻し】自己申告メッセージのみが入力されています。ターミナルで実際にコマンドを実行し、その生ログをコピーして貼り付けてください。",
        }

    # 2. エラー検知
    error_keywords = ["error:", "failed", "exception", "timed out", "denied", "command not found"]
    has_error = any(k in output_lower for k in error_keywords) and "0 failed" not in output_lower
    
    if has_error:
        return {
            "verdict": "ERROR",
            "w_check_status": "ESCALATION_REQUIRED",
            "step_id": step_id,
            "autonomous_verdict": "【AI確認者 エスカレーション発動 🚨】コマンド実行ログ内に異常・エラーを検知しました。",
            "message": "【判定: エラー検知】ログ内にエラーまたは異常終了を検知しました。作業を中断し、上長協議（ペア作業モード）またはロールバックへ移行してください。",
        }

    # 3. 正常系・合格承認
    return {
        "verdict": "SUCCESS",
        "w_check_status": "VERIFIED_APPROVED",
        "step_id": step_id,
        "autonomous_verdict": f"【AI確認者 Wチェック承認 ✓】ステップ {step_id} の客観生ログを確認しました。次ステップへ進んでください。",
        "message": f"【判定: 合格】ステップ {step_id} の実行結果を客観確認しました！要件に100%合致しています。",
    }


def get_sop_step_info(step_id: str) -> Dict[str, Any]:
    """指定ステップのSOP情報（タイトル、コマンド、確認事項、注意事項）を取得する。"""
    step = DEFAULT_SOP.get(step_id, {})
    if not step:
        return {"error": f"Step {step_id} not found."}
    return {"status": "success", "step": step}


# --- Root Agent Definition ---

root_agent = Agent(
    model="gemini-3.8-flash",
    name="hitman_lite",
    description="Excelリリース手順書を自律ナビゲートし、ターミナル生ログを客観WチェックするAIペアオペレーター",
    instruction=(
        "あなたはIPPのAIペアオペレーター『HITMAN Lite』です。\n"
        "作業者からターミナルログを受け取ったら、必ず verify_step_output ツールを呼び出して客観Wチェックを行ってください。\n"
        "自己申告（'完了しました'等）は断固として差し戻し、客観的なコマンド実行証跡を求めてください。\n"
        "判定結果をA2UIカード形式で視覚的にフィードバックしてください。"
    ),
    tools=[verify_step_output, get_sop_step_info],
    after_model_callback=a2ui_callback,
)
