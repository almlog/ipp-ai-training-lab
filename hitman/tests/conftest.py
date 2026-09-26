import os
from dotenv import load_dotenv

# Load .env for all pytest tests
load_dotenv('.env')


import pytest


@pytest.fixture(autouse=True)
def _reset_hitman_global_state():
    """テスト間でモジュールグローバル（ToolContext なし呼び出し用のフォールバック状態）が漏れないよう毎回初期化する。"""
    try:
        import app.agent as agent_module
        agent_module.reset_active_sop()
    except Exception:
        pass
    yield
