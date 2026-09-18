# Copyright (c) 2026 Shunpei Suzuki (suzuki.shunpei@ipp.local), IPP
# Developed by Shunpei Suzuki <suzuki.shunpei@ipp.local>
#
"""Unit tests for Excel (.xlsm / .xlsx) SOP parsing and API endpoints."""

import os
import io
import pytest
from fastapi.testclient import TestClient
from app.excel_parser import parse_excel_sop
from app.agent import (
    import_excel_sop_procedure,
    get_active_sop,
    get_active_parameters,
    get_active_approval,
    get_active_branch_rules,
    reset_active_sop,
)
from frontend.main import app

client = TestClient(app)

_base_knowledge = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "knowledge",
)
SAMPLE_XLSM_PATH = os.path.join(_base_knowledge, "standard_web_release_sop_v2.1.xlsm")
if not os.path.exists(SAMPLE_XLSM_PATH):
    SAMPLE_XLSM_PATH = os.path.join(_base_knowledge, "現場標準_Webアプリ本番リリース手順書_v2.1.xlsm")


def test_parse_sample_xlsm():
    """Verify that sample .xlsm is successfully parsed with all metadata and parameters."""
    assert os.path.exists(SAMPLE_XLSM_PATH), f"Sample file not found at {SAMPLE_XLSM_PATH}"
    
    res = parse_excel_sop(SAMPLE_XLSM_PATH)
    assert res["status"] == "success"
    assert res["imported_steps_count"] == 10
    assert len(res["step_sequence"]) == 10
    
    # 承認メタデータ検証
    approval = res["approval_metadata"]
    assert approval["is_approved"] is True
    assert "山田 太郎" in approval["approver"]
    assert "鈴木 駿平" in approval["author"]
    assert "APPR-20260906-IPP-01" in approval["approval_id"]
    assert "2026-09-06" in approval["approval_date"]
    
    # パラメータ抽出と変数置換検証
    params = res["parameters"]
    assert params["TARGET_HOST"] == "db-prd-01.internal.ipp.local"
    assert params["HEALTH_PORT"] == "8080"
    assert params["APP_VERSION"] == "v2.1.0"
    assert params["BACKUP_DIR"] == "/backup/20260906_release"
    assert params["TARGET_TENANT"] == "T100"
    
    # コマンド内の変数展開検証
    step1 = res["sop_database"][1]["sub_steps"]["1-1"]
    assert "df -h /backup/20260906_release" in step1["command"]
    assert "${BACKUP_DIR}" not in step1["command"]
    
    step2 = res["sop_database"][2]["sub_steps"]["2-1"]
    assert "http://db-prd-01.internal.ipp.local:8080/health" in step2["command"]
    assert "${TARGET_HOST}" not in step2["command"]
    
    # 分岐ルール検証 (R-1, E-1)
    branch_rules = res["branch_rules"]
    assert "1-2" in branch_rules
    assert branch_rules["1-2"].get("on_failure") == "R-1"
    assert "2-1" in branch_rules
    assert branch_rules["2-1"].get("on_mismatch") == "E-1"


def test_import_excel_sop_agent_state():
    """Verify that import_excel_sop_procedure updates active state in agent.py."""
    reset_active_sop()
    
    res = import_excel_sop_procedure(SAMPLE_XLSM_PATH)
    assert res["status"] == "success"
    
    active_params = get_active_parameters()
    assert active_params.get("TARGET_HOST") == "db-prd-01.internal.ipp.local"
    assert active_params.get("BACKUP_DIR") == "/backup/20260906_release"
    
    active_approval = get_active_approval()
    assert active_approval["is_approved"] is True
    assert "山田 太郎" in active_approval["approver"]
    
    active_sop = get_active_sop()
    assert 1 in active_sop
    assert "1-1" in active_sop[1]["sub_steps"]
    
    reset_active_sop()


def test_api_sop_upload_excel_endpoint():
    """Verify POST /api/sop/upload-excel endpoint."""
    with open(SAMPLE_XLSM_PATH, "rb") as f:
        file_bytes = f.read()
    
    response = client.post(
        "/api/sop/upload-excel",
        files={"file": ("現場標準_Webアプリ本番リリース手順書_v2.1.xlsm", file_bytes, "application/vnd.ms-excel.sheet.macroEnabled.12")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["status"] == "success"
    assert "parameters" in data
    assert data["parameters"]["TARGET_HOST"] == "db-prd-01.internal.ipp.local"
    assert data["approval"]["is_approved"] is True
    assert "山田 太郎" in data["approval"]["approver"]
    assert len(data["sequence"]) == 10
    
    # Clean up
    reset_active_sop()


def test_api_sop_sample_xlsm_download():
    """Verify GET /api/sop/sample-xlsm endpoint downloads the file."""
    response = client.get("/api/sop/sample-xlsm")
    assert response.status_code == 200
    assert "application/vnd.ms-excel.sheet.macroEnabled.12" in response.headers["content-type"]
    assert len(response.content) > 1000
