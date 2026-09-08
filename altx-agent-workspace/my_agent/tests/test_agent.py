"""
Tests for Rubik's Cube Solver Agent (rubik-solver-agent)
"""

import sys
import os

# Add my_agent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent import analyze_cube_state, calculate_solving_route, root_agent

def test_analyze_cube_state():
    """3面写真・配色データのパリティ整合性検証テスト"""
    res = analyze_cube_state()
    assert res["status"] == "VALID"
    assert res["total_tiles_analyzed"] == 54
    assert res["faces_detected"] == 3
    assert "U (上面)" in res["center_pieces"]
    assert res["estimated_distance_to_solved"] > 0

def test_calculate_solving_route_beginner():
    """初心者向けLBL解法ルートの算出テスト"""
    res = calculate_solving_route(difficulty="beginner")
    assert "初心者向けLBL法" in res["strategy"]
    assert res["total_moves"] > 0
    assert len(res["steps"]) == 4
    # ステップ1がホワイトクロスであること
    assert "ホワイトクロス" in res["steps"][0]["stage"]
    assert "PLL" in res["steps"][3]["stage"]

def test_calculate_solving_route_cfop():
    """中上級者向けCFOP最短解法ルートの算出テスト"""
    res = calculate_solving_route(difficulty="cfop")
    assert "CFOP法" in res["strategy"]
    assert res["total_moves"] > 0
    assert "D'" in res["full_notation"]

def test_root_agent_configuration():
    """ADKエージェント設定・A2UIコールバック設定の検証"""
    assert root_agent.name == "rubik_solver_agent"
    assert len(root_agent.tools) == 2
    assert root_agent.after_model_callback is not None
