from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UI_AUDIT_SCRIPT = ROOT / ".agents" / "skills" / "ipp-build-app-from-brief" / "scripts" / "ui_audit.py"

sys.path.insert(0, str(UI_AUDIT_SCRIPT.parent))
from ui_audit import audit_html  # noqa: E402


def test_ui_audit_script_exists():
    assert UI_AUDIT_SCRIPT.is_file(), f"{UI_AUDIT_SCRIPT} does not exist"


def test_plain_ugly_html_fails():
    ugly_html = """<!DOCTYPE html>
<html>
<head>
    <title>Ugly Plain App</title>
</head>
<body>
    <h1>My Calendar App</h1>
    <table border="1">
        <tr><td>2026-09-30</td><td>Meeting</td></tr>
    </table>
    <input type="text" id="task">
    <button onclick="alert('add')">Add</button>
</body>
</html>
"""
    result = audit_html(ugly_html)
    assert not result["passed"]
    assert result["score"] < 80
    assert "MISSING" in result["details"]["google_fonts"]
    assert "MISSING" in result["details"]["material_symbols"]
    assert "MISSING" in result["details"]["styling"]
    assert len(result["suggestions"]) > 0


def test_google_rich_ui_html_passes():
    rich_html = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Standard Rich Calendar</title>
    <!-- Google Fonts: Noto Sans JP -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
    <!-- Material Symbols -->
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans min-h-screen">
    <div class="max-w-4xl mx-auto p-6">
        <header class="flex items-center justify-between mb-8">
            <h1 class="text-2xl font-bold flex items-center gap-2">
                <span class="material-symbols-outlined text-blue-600">calendar_month</span>
                スマートスケジュール管理
            </h1>
        </header>
        <div class="bg-white rounded-xl shadow-md p-6 border border-slate-200">
            <h2 class="text-lg font-semibold mb-4">タスク一覧</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="p-4 bg-slate-50 rounded-lg border border-slate-100 shadow-sm">
                    <p class="font-medium">研修レビュー</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    result = audit_html(rich_html)
    assert result["passed"]
    assert result["score"] >= 80
    assert "PASS" in result["details"]["google_fonts"]
    assert "PASS" in result["details"]["material_symbols"]
    assert "PASS" in result["details"]["styling"]
    assert "PASS" in result["details"]["components"]
    assert "PASS" in result["details"]["viewport"]


def test_ui_audit_cli(tmp_path):
    ugly_file = tmp_path / "ugly.html"
    ugly_file.write_text("<html><body><h1>plain</h1></body></html>", encoding="utf-8")

    proc_ugly = subprocess.run(
        [sys.executable, str(UI_AUDIT_SCRIPT), "--file", str(ugly_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_ugly.returncode != 0
    assert "UI_AUDIT_RESULT: FAIL" in proc_ugly.stdout

    rich_file = tmp_path / "rich.html"
    rich_file.write_text("""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Roboto&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" />
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100">
<div class="card rounded-lg shadow p-4 bg-white">Hello</div>
</body>
</html>""", encoding="utf-8")

    proc_rich = subprocess.run(
        [sys.executable, str(UI_AUDIT_SCRIPT), "--file", str(rich_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc_rich.returncode == 0
    assert "UI_AUDIT_RESULT: PASS" in proc_rich.stdout
