# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
# Developed by Shunpei Suzuki <suzuki.shunpei@ipp.local>
"""Unit tests for Code Metrics & Hand-off/Rework Prevention ROI Calculation."""

import os
import tempfile
import pytest
from app.code_metrics import (
    calculate_rework_prevention_roi,
    extract_quality_metrics,
    scan_workspace_directory,
    get_participant_code_metrics,
)


def test_calculate_rework_prevention_roi_training_dynamic():
    """Verify that rework prevention hours and ROI vary dynamically based on LOC, files, and quality."""
    # Small / baseline project
    small = calculate_rework_prevention_roi(
        total_loc=300,
        total_files=4,
        ui_audit_score=80,
        passed_tests=2,
        cloud_deployed=False,
        hourly_rate=5000,
    )
    # Medium project (e.g. 650 LOC, 6 files, 88 pts, 3 tests, deployed)
    med = calculate_rework_prevention_roi(
        total_loc=650,
        total_files=6,
        ui_audit_score=88,
        passed_tests=3,
        cloud_deployed=True,
        hourly_rate=5000,
    )
    # Large / complex project (1200 LOC, 10 files, 95 pts, 6 tests, deployed)
    large = calculate_rework_prevention_roi(
        total_loc=1200,
        total_files=10,
        ui_audit_score=95,
        passed_tests=6,
        cloud_deployed=True,
        hourly_rate=5000,
    )

    # 1. Total saved hours must strictly increase with code volume & complexity
    assert med["total_saved_hours"] > small["total_saved_hours"]
    assert large["total_saved_hours"] > med["total_saved_hours"]

    # 2. Financial savings must equal saved_hours * hourly_rate
    assert med["saved_cost_jpy"] == int(med["total_saved_hours"] * 5000)
    assert large["saved_cost_jpy"] == int(large["total_saved_hours"] * 5000)

    # 3. Breakdown must exist and be transparent
    assert "code_debug_rework" in med["hours_breakdown"]
    assert "architecture_integration" in med["hours_breakdown"]
    assert "ui_polish_accessibility" in med["hours_breakdown"]
    assert "test_mock_design" in med["hours_breakdown"]
    assert "cloud_iam_secret_deploy" in med["hours_breakdown"]
    assert med["hours_breakdown"]["cloud_iam_secret_deploy"] == 3.5
    assert small["hours_breakdown"]["cloud_iam_secret_deploy"] == 0.0


def test_scan_workspace_directory():
    """Verify directory scanner correctly categorizes python, html, and config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock agent files
        with open(os.path.join(tmpdir, "agent.py"), "w", encoding="utf-8") as f:
            f.write("# agent code\nimport os\nprint('hello')\n")
        with open(os.path.join(tmpdir, "index.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html>\n<html>\n<body>\n<h1>UI</h1>\n</body>\n</html>\n")
        with open(os.path.join(tmpdir, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write("FROM python:3.12-slim\nEXPOSE 8080\n")
        os.makedirs(os.path.join(tmpdir, "tests"), exist_ok=True)
        with open(os.path.join(tmpdir, "tests", "test_agent.py"), "w", encoding="utf-8") as f:
            f.write("def test_ok():\n    assert True\n")

        res = scan_workspace_directory(tmpdir)
        assert res["total_files"] == 4
        assert res["total_loc"] >= 10
        assert res["categories"]["python"]["files"] == 1
        assert res["categories"]["frontend"]["files"] == 1
        assert res["categories"]["config"]["files"] == 1
        assert res["categories"]["test"]["files"] == 1


def test_extract_quality_metrics():
    """Verify extraction of UI audit score and pytest count from step logs."""
    sop_results = {
        "T-3": {"verdict": "SUCCESS", "logSnippet": "UI_AUDIT: PASSED (92点 / Google Fonts & Tailwind適用)"},
        "T-4": {"verdict": "SUCCESS", "logSnippet": "=== 5 passed in 0.42s ==="},
        "T-5": {"verdict": "SUCCESS", "logSnippet": "Cloud Run deployed successfully"},
        "T-6": {"verdict": "SUCCESS", "logSnippet": "CLEANUP_RESULT: SUCCESS"},
    }
    q = extract_quality_metrics(sop_results)
    assert q["ui_audit_score"] == 92
    assert q["passed_tests"] == 5
    assert q["cloud_deployed"] is True
    assert q["cleanup_done"] is True


def test_api_code_metrics_endpoint():
    """Verify /api/training/code-metrics endpoint via TestClient."""
    from fastapi.testclient import TestClient
    from frontend.main import app

    client = TestClient(app)
    res = client.post(
        "/api/training/code-metrics",
        json={
            "user_id": "test-user-metrics",
            "agent_slug": "log_analyzer_bot",
            "sop_results": {
                "T-3": {"verdict": "SUCCESS", "logSnippet": "UIスコア 90点"},
                "T-4": {"verdict": "SUCCESS", "logSnippet": "3 passed"},
                "T-5": {"verdict": "SUCCESS"},
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "roi" in data
    assert data["roi"]["hourly_rate"] == 5000
    assert data["roi"]["total_saved_hours"] > 10.0
    assert data["roi"]["saved_cost_jpy"] > 50000
