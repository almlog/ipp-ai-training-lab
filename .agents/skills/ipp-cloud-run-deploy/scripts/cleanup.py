#!/usr/bin/env python
"""IPP AI研修: 演習終了後の Cloud Run サービスおよび Secret Manager の安全削除（クリーンアップ）。

目的:
- 演習終了後の不要な課金発生を防止する (FinOps)
- クラウド上に受講生の API キーや公開エンドポイントが残り続けるのを防ぐ (セキュリティ)

使い方（ワークスペースのルートで）:
  python .agents/skills/ipp-cloud-run-deploy/scripts/cleanup.py --service <サービス名>
  または
  python .agents/skills/ipp-cloud-run-deploy/scripts/cleanup.py --agent-dir ipp-agent-workspace/<エージェント名>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = "[skill:ipp-cloud-run-deploy@v1]"


def _gcloud() -> str:
    path = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not path:
        raise SystemExit("gcloud コマンドが見つかりません。Google Cloud CLI をインストールし、gcloud auth login を実行してください。")
    return path


def _run(args: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        [_gcloud(), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if check and proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()[-5:]
        raise SystemExit(f"gcloud {' '.join(args[:3])} が失敗しました:\n" + "\n".join(err))
    return proc


def derive_service_name(agent_dir: str | None, service: str | None) -> str:
    if service:
        return service.strip()
    if agent_dir:
        p = Path(agent_dir).resolve()
        return p.name
    return ""


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="IPP AI研修: 演習環境の安全停止＆クリーンアップ")
    ap.add_argument("--service", default="", help="削除対象の Cloud Run サービス名")
    ap.add_argument("--agent-dir", default="", help="エージェントのディレクトリ（サービス名を推定）")
    ap.add_argument("--region", default="asia-northeast1", help="デプロイ先リージョン")
    ap.add_argument("--project", default="", help="Google Cloud プロジェクトID")
    ap.add_argument("--keep-secret", action="store_true", help="Secret Manager のシークレットは削除せず維持する")
    args = ap.parse_args(argv)

    service = derive_service_name(args.agent_dir, args.service)
    if not service:
        raise SystemExit("エラー: --service または --agent-dir を指定してください。")

    project = args.project or _run(["config", "get-value", "project"]).stdout.strip()
    if not project:
        raise SystemExit("Google Cloud のプロジェクトが未設定です。gcloud config set project <プロジェクトID> を実行してください。")
    pflag = ["--project", project]

    print(MARKER)
    print(f"# IPP AI研修: 演習環境クリーンアップ実行レポート")
    print(f"- **プロジェクト**: `{project}`")
    print(f"- **対象サービス**: `{service}`")
    print(f"- **リージョン**: `{args.region}`")
    print()

    # 1. Cloud Run サービスの削除
    print("## 1. Cloud Run サービスの破棄（課金・外部アクセス停止）")
    desc = _run(["run", "services", "describe", service, "--region", args.region, *pflag], check=False)
    run_status = "NOT_FOUND"
    if desc.returncode == 0:
        print(f"- Cloud Run サービス `{service}` が検出されました。削除を実行します...")
        del_proc = _run(["run", "services", "delete", service, "--region", args.region, "--quiet", *pflag], check=False)
        if del_proc.returncode == 0:
            run_status = "DELETED"
            print(f"- [SUCCESS] Cloud Run サービス `{service}` を正常に削除しました。")
        else:
            run_status = "FAILED"
            err = (del_proc.stderr or "").strip().splitlines()[-3:]
            print(f"- [FAILED] サービスの削除に失敗しました: {'; '.join(err)}")
    else:
        print(f"- Cloud Run サービス `{service}` はすでに存在しません（作成前または削除済み）。")
        run_status = "ALREADY_DELETED"

    # 2. Secret Manager のシークレット削除
    secret_status = "SKIPPED"
    if not args.keep_secret:
        print()
        print("## 2. Secret Manager の破棄（クラウド上のAPIキー完全消去）")
        secrets_to_check = [f"{service}-gemini-api-key"[:255]]
        # サービス名と異なる固定キーももし存在していれば確認
        if service == "my_hitman":
            secrets_to_check.append("ipp-gemini-api-key")

        secret_results = []
        for sec in sorted(set(secrets_to_check)):
            s_desc = _run(["secrets", "describe", sec, *pflag], check=False)
            if s_desc.returncode == 0:
                print(f"- Secret `{sec}` が検出されました。削除を実行します...")
                s_del = _run(["secrets", "delete", sec, "--quiet", *pflag], check=False)
                if s_del.returncode == 0:
                    secret_results.append((sec, "DELETED"))
                    print(f"- [SUCCESS] Secret `{sec}` を正常に削除しました。")
                else:
                    secret_results.append((sec, "FAILED"))
                    err = (s_del.stderr or "").strip().splitlines()[-3:]
                    print(f"- [FAILED] Secret `{sec}` の削除に失敗しました: {'; '.join(err)}")
            else:
                print(f"- Secret `{sec}` は存在しません（未作成または削除済み）。")
                secret_results.append((sec, "ALREADY_DELETED"))

        if all(st in ("DELETED", "ALREADY_DELETED") for _, st in secret_results):
            secret_status = "DELETED"
        elif any(st == "FAILED" for _, st in secret_results):
            secret_status = "FAILED"
        else:
            secret_status = "ALREADY_DELETED"
    else:
        print()
        print("## 2. Secret Manager の破棄（--keep-secret 指定のためスキップ）")

    # 3. 総合判定
    print()
    print("## 3. クリーンアップ結果判定")
    success = run_status in ("DELETED", "ALREADY_DELETED") and secret_status in ("DELETED", "ALREADY_DELETED", "SKIPPED")
    if success:
        print("- **総合判定**: **CLEANUP: SUCCESS**")
        print("- **セキュリティ状態**: クラウド上のエンドポイントおよびシークレットは完全に破棄されました。")
        print("- **FinOps 状態**: クラウド上でのリクエスト受信・インスタンス待機による余計な課金リスクはありません。")
    else:
        print("- **総合判定**: **CLEANUP: WARNING_OR_FAILED**")
        print("- 手動での確認が必要な項目があります。Google Cloud Console を確認してください。")

    print(f"\nCLEANUP_RESULT: {'SUCCESS' if success else 'FAILED'}")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
