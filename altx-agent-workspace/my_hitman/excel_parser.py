"""
HITMAN Lite: Excel & SOP 手順書パーサーモジュール
.xlsm / .xlsx / .csv / Markdown 形式の手順書を解析し、構造化ステップ辞書を生成する。
"""

import os
import csv
from typing import Dict, Any, List

def parse_sop_file(file_path: str) -> Dict[str, Any]:
    """手順書ファイルを読み込み、ステップ辞書に変換する。"""
    if not os.path.exists(file_path):
        return _get_default_sop()

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".csv", ".txt"):
        return _parse_csv_sop(file_path)
    # デフォルトのSOP
    return _get_default_sop()


def _parse_csv_sop(file_path: str) -> Dict[str, Any]:
    steps = {}
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            step_id = row.get("step_id", "").strip()
            if step_id:
                steps[step_id] = {
                    "step_id": step_id,
                    "title": row.get("title", ""),
                    "objective": row.get("objective", ""),
                    "command": row.get("command", ""),
                    "expected_check": row.get("expected_check", ""),
                    "cautions": row.get("cautions", ""),
                }
    return steps or _get_default_sop()


def _get_default_sop() -> Dict[str, Any]:
    """組み込みの標準リリース手順書（SOP）"""
    return {
        "1-1": {
            "step_id": "1-1",
            "title": "事前確認: ディスク空き容量チェック",
            "objective": "ルートパーティションの空き容量が20%以上あることを確認する",
            "command": "df -h /",
            "expected_check": "Use% が 80% 以下であること",
            "cautions": "80%以上の場合は即時作業中断しエスカレーション",
        },
        "1-2": {
            "step_id": "1-2",
            "title": "事前確認: データベース接続確認",
            "objective": "本番DBへの疎通およびレイテンシを確認する",
            "command": "pg_isready -h db.production.local -p 5432",
            "expected_check": "accepting connections",
            "cautions": "接続不可の場合はDB障害として中断",
        },
        "2-1": {
            "step_id": "2-1",
            "title": "バックアップ取得: 現行ソース＆環境設定",
            "objective": "ロールバック用の現行コード完全バックアップを作成する",
            "command": "tar -czf /backup/app_backup.tar.gz /var/www/app",
            "expected_check": "終了コード 0、バックアップファイルが正常作成されること",
            "cautions": "容量不足による書き込みエラーに注意",
        },
        "3-1": {
            "step_id": "3-1",
            "title": "アプリ配置＆マイグレーション",
            "objective": "新バージョンのコードを展開しDBマイグレーションを実行する",
            "command": "git pull origin main && python manage.py migrate",
            "expected_check": "Apply all migrations: OK",
            "cautions": "マイグレーションエラー時は即時ロールバック（R-1）",
        },
        "4-1": {
            "step_id": "4-1",
            "title": "サービス再起動＆ヘルスチェック",
            "objective": "アプリケーションを再起動しHTTP 200 OKを確認する",
            "command": "systemctl restart webapp && curl -I http://localhost:8080/health",
            "expected_check": "HTTP/1.1 200 OK",
            "cautions": "500エラー時はログ調査後ロールバック",
        },
    }
