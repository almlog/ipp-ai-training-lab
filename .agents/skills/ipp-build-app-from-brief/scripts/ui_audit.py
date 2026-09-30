#!/usr/bin/env python
"""IPP AI研修: Google標準リッチUI品質監査スクリプト (UI Quality Audit)

目的:
- 受講生（AntiGravity）が作成した Web アプリの画面（HTML）が、
  「素のダサい・使えないHTML」ではなく「Google標準のリッチなUI」の基準を満たしているかを客観検証する。
- 基準未達の場合は具体的な改善スニペットを提示し、AntiGravity による自律修正を促す。

合格基準 (80点以上で PASS):
1. Google Fonts の導入 (Roboto, Google Sans, Noto Sans JP等) [20点]
2. Material Symbols / Icons の導入 (material-symbols-outlined等) [20点]
3. スタイリングフレームワーク (Tailwind CSS または体系的モダンCSS) [25点]
4. カード型レイアウト ＆ コンポーネント設計 (rounded, shadow, card構造) [20点]
5. レスポンシブ設計 (meta viewport) [15点]

使い方:
  python .agents/skills/ipp-build-app-from-brief/scripts/ui_audit.py --agent-dir ipp-agent-workspace/<エージェント名>
  または
  python .agents/skills/ipp-build-app-from-brief/scripts/ui_audit.py --file path/to/index.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MARKER = "[skill:ipp-build-app-from-brief@v1]"


def audit_html(html_text: str) -> dict:
    """HTMLテキストを静的解析し、Google標準リッチUI基準を採点する。"""
    scores = {}
    details = {}
    suggestions = []

    # 1. レスポンシブ Viewport (15点)
    has_viewport = bool(re.search(r'<meta\s+[^>]*name=[\'"]viewport[\'"][^>]*>', html_text, re.IGNORECASE))
    scores["viewport"] = 15 if has_viewport else 0
    details["viewport"] = "PASS (<meta name=\"viewport\"> 設定済)" if has_viewport else "MISSING (<meta name=\"viewport\"> がありません)"
    if not has_viewport:
        suggestions.append('<meta name="viewport" content="width=device-width, initial-scale=1.0"> を <head> に追加してください。')

    # 2. Google Fonts (20点)
    has_gfonts = bool(re.search(r'fonts\.googleapis\.com|fonts\.gstatic\.com', html_text, re.IGNORECASE))
    scores["google_fonts"] = 20 if has_gfonts else 0
    details["google_fonts"] = "PASS (Google Fonts 導入済)" if has_gfonts else "MISSING (Google Fonts 未導入: ブラウザ標準フォント)"
    if not has_gfonts:
        suggestions.append('<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet"> を追加してください。')

    # 3. Material Symbols / Icons (20点)
    has_icons = bool(re.search(r'material-symbols|material-icons', html_text, re.IGNORECASE))
    scores["material_symbols"] = 20 if has_icons else 0
    details["material_symbols"] = "PASS (Material Symbols/Icons 導入済)" if has_icons else "MISSING (アイコン未導入)"
    if not has_icons:
        suggestions.append('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" /> を追加し、ボタンや見出しにアイコンを配置してください。')

    # 4. スタイリングフレームワーク (Tailwind CSS または体系的モダンCSS) (25点)
    has_tailwind = bool(re.search(r'cdn\.tailwindcss\.com|tailwindcss', html_text, re.IGNORECASE))
    has_rich_style = False
    if not has_tailwind:
        # style タグ内の CSS ルール数を簡易判定
        style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_text, re.DOTALL | re.IGNORECASE)
        combined_css = " ".join(style_matches)
        css_rules = len(re.findall(r'[\w-]+\s*:\s*[^;]+;', combined_css))
        has_flex_or_grid = bool(re.search(r'display\s*:\s*(flex|grid)', combined_css, re.IGNORECASE))
        has_rich_style = css_rules >= 12 and has_flex_or_grid

    if has_tailwind:
        scores["styling"] = 25
        details["styling"] = "PASS (Tailwind CSS 導入済)"
    elif has_rich_style:
        scores["styling"] = 20
        details["styling"] = "PASS (体系的なモダン CSS 適用済)"
    else:
        scores["styling"] = 0
        details["styling"] = "MISSING (Tailwind またはモダン CSS 未適用: ダサい素のHTML)"
        suggestions.append('<script src="https://cdn.tailwindcss.com"></script> を <head> に導入し、モダンなスタイリングを適用してください。')

    # 5. カード型レイアウト ＆ コンポーネントUI (20点)
    # rounded / shadow / card / border-radius / flex / grid
    has_card = bool(re.search(r'\b(rounded|shadow|card|bg-white|border|p-\d|p-[a-z\d]+)\b', html_text, re.IGNORECASE))
    has_css_cards = bool(re.search(r'border-radius|box-shadow', html_text, re.IGNORECASE))
    if has_card or has_css_cards:
        scores["components"] = 20
        details["components"] = "PASS (カード型レイアウト・余白・角丸・影が設定済)"
    else:
        scores["components"] = 0
        details["components"] = "MISSING (コンポーネント装飾なし: 平坦な素のHTML)"
        suggestions.append('背景色(bg-slate-50等)、カード枠(rounded-lg shadow-md bg-white p-6)、ボタン装飾を適用してください。')

    total_score = sum(scores.values())
    passed = total_score >= 80

    return {
        "passed": passed,
        "score": total_score,
        "details": details,
        "suggestions": suggestions,
    }


def find_html_file(agent_dir: Path | None, file_arg: str | None) -> Path | None:
    if file_arg:
        p = Path(file_arg).resolve()
        if p.is_file():
            return p
    if agent_dir and agent_dir.is_dir():
        candidates = [
            agent_dir / "static" / "index.html",
            agent_dir / "templates" / "index.html",
            agent_dir / "index.html",
        ]
        for c in candidates:
            if c.is_file():
                return c
        for h in agent_dir.rglob("*.html"):
            return h
    return None


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="IPP AI研修: Google標準リッチUI品質監査")
    ap.add_argument("--agent-dir", default="", help="エージェントディレクトリ")
    ap.add_argument("--file", default="", help="検証対象のHTMLファイルパス")
    args = ap.parse_args(argv)

    agent_dir = Path(args.agent_dir).resolve() if args.agent_dir else None
    html_file = find_html_file(agent_dir, args.file)

    print(MARKER)
    print("# IPP AI研修: Google標準リッチUI 品質監査レポート")
    if not html_file or not html_file.is_file():
        print(f"- **対象HTML**: 検出失敗 (agent_dir={args.agent_dir}, file={args.file})")
        print("\nUI_AUDIT_RESULT: FAIL")
        print("Reason: 検査対象の HTML ファイル（static/index.html）が見つかりません。")
        return 1

    print(f"- **対象ファイル**: `{html_file}`")
    html_content = html_file.read_text(encoding="utf-8", errors="replace")
    audit = audit_html(html_content)

    print(f"- **品質スコア**: **{audit['score']} / 100 点**")
    print(f"- **総合判定**: **{'UI_AUDIT: PASS ✓' if audit['passed'] else 'UI_AUDIT: FAIL ✗'}**")
    print()
    print("## 評価項目詳細")
    for k, v in audit["details"].items():
        print(f"- **{k}**: {v}")

    if not audit["passed"]:
        print()
        print("## ❌ 改善が必要な項目 (Google標準リッチUIへのブラッシュアップ)")
        for s in audit["suggestions"]:
            print(f"- {s}")
        print()
        print("### 💡 推奨 <head> テンプレート (コピーして利用可能):")
        print("```html")
        print("<head>")
        print('  <meta charset="UTF-8">')
        print('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        print('  <title>App Title</title>')
        print('  <!-- Google Fonts: Noto Sans JP -->')
        print('  <link rel="preconnect" href="https://fonts.googleapis.com">')
        print('  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
        print('  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">')
        print('  <!-- Material Symbols -->')
        print('  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />')
        print('  <!-- Tailwind CSS -->')
        print('  <script src="https://cdn.tailwindcss.com"></script>')
        print("</head>")
        print("```")
        print()
        print("UI_AUDIT_RESULT: FAIL")
        return 1

    print()
    print("## ✓ Google標準リッチUI 品質基準クリア")
    print("- 美しいタイポグラフィ、マテリアルアイコン、モダンCSSフレームワーク、カード型コンポーネントが確認されました。")
    print("\nUI_AUDIT_RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
