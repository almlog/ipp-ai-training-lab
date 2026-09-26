"""
社内障害ログ自動解析Bot（log-analyzer-bot）— IPP AI研修 コースA 見本
Google ADK (Agent Development Kit) + A2UI Rich Cards

ツールは入力（ログ本文）を実際に解析して結果を返す。固定値を返すダミー実装ではない。
ステップ T-3 のスモークテスト（ipp-agent-smoke-test）では、異なるログを渡すと
異なる解析結果・推奨コマンドが返ることが確認される。
"""

from __future__ import annotations

import re

from google.adk.agents import Agent

from a2ui_utils import a2ui_callback

MODEL = "gemini-3.8-flash"  # 利用できない場合は gemini-3.6-flash

# エラー分類ルール（上から順に評価。最初に一致したものを採用）
_ERROR_RULES: list[dict] = [
    {"type": "DISK_FULL", "severity": "CRITICAL", "patterns": [r"no space left on device", r"disk quota exceeded", r"ディスク.*(不足|枯渇)"],
     "cause": "ディスク容量の枯渇"},
    {"type": "OUT_OF_MEMORY", "severity": "CRITICAL", "patterns": [r"out ?of ?memory", r"oom-?kill", r"cannot allocate memory", r"memoryerror"],
     "cause": "メモリ不足（OOM）"},
    {"type": "DB_CONNECTION", "severity": "CRITICAL", "patterns": [r"connection refused.*(5432|3306)", r"could not connect to (the )?(database|server)",
                                                                   r"(db|database|connection).*timeout", r"timeout.*(db|database|connection)", r"too many connections"],
     "cause": "データベースへの接続失敗（停止・過負荷・接続上限）"},
    {"type": "DB_LOCK", "severity": "WARNING", "patterns": [r"deadlock", r"lock wait timeout"],
     "cause": "データベースのロック競合"},
    {"type": "PERMISSION", "severity": "WARNING", "patterns": [r"permission denied", r"access denied", r"\b403\b", r"eacces"],
     "cause": "権限不足（ファイル権限・IAM・認可）"},
    {"type": "NETWORK", "severity": "WARNING", "patterns": [r"connection reset", r"name or service not known", r"getaddrinfo", r"econnrefused", r"\b50[234]\b"],
     "cause": "ネットワーク・上流サービスの到達不可"},
    {"type": "APPLICATION_EXCEPTION", "severity": "WARNING", "patterns": [r"traceback \(most recent call last\)", r"exception", r"\berror\b"],
     "cause": "アプリケーション内部の例外"},
]

# エラー種別ごとの一次切り分けコマンド（読み取り専用の調査コマンドを先に、変更を伴う操作は注意書き付き）
_FIX_COMMANDS: dict[str, list[dict]] = {
    "DISK_FULL": [
        {"cmd": "df -h", "note": "どのファイルシステムが満杯か確認"},
        {"cmd": "du -xh /var/log | sort -h | tail -n 20", "note": "大きいログファイルを特定"},
        {"cmd": "journalctl --vacuum-time=7d", "note": "【変更あり】7日より古い journal を削除（上長承認のうえ実行）"},
    ],
    "OUT_OF_MEMORY": [
        {"cmd": "free -h", "note": "メモリ残量を確認"},
        {"cmd": "dmesg -T | grep -i -E 'killed process|out of memory' | tail", "note": "OOM Killer の発動履歴を確認"},
        {"cmd": "systemctl restart {service}", "note": "【変更あり】サービス再起動（影響範囲を確認のうえ実行）"},
    ],
    "DB_CONNECTION": [
        {"cmd": "systemctl status postgresql", "note": "DB プロセスの稼働状況を確認（MySQL は mysqld）"},
        {"cmd": "psql -h <DBホスト> -U app_user -c 'select 1'", "note": "アプリサーバから DB へ疎通確認"},
        {"cmd": "psql -c \"select count(*) from pg_stat_activity\"", "note": "接続数が上限に達していないか確認"},
    ],
    "DB_LOCK": [
        {"cmd": "psql -c \"select pid, state, wait_event_type, query from pg_stat_activity where wait_event_type = 'Lock'\"", "note": "ロック待ちのセッションを確認"},
        {"cmd": "SHOW ENGINE INNODB STATUS\\G", "note": "MySQL の場合: 直近のデッドロック情報を確認"},
    ],
    "PERMISSION": [
        {"cmd": "ls -l <対象パス>", "note": "ファイルの所有者・権限を確認"},
        {"cmd": "id {service}", "note": "サービス実行ユーザーの所属グループを確認"},
        {"cmd": "gcloud projects get-iam-policy <PROJECT_ID> --format=json | head -n 50", "note": "GCP の場合: IAM ロールを確認"},
    ],
    "NETWORK": [
        {"cmd": "curl -sS -o /dev/null -w '%{{http_code}}' <上流URL>", "note": "上流サービスの応答コードを確認"},
        {"cmd": "nslookup <ホスト名>", "note": "名前解決を確認"},
    ],
    "APPLICATION_EXCEPTION": [
        {"cmd": "journalctl -u {service} --since '15 min ago' | tail -n 100", "note": "直近15分のアプリログを確認"},
        {"cmd": "git log --oneline -5", "note": "直近のデプロイ変更を確認（リリース起因か切り分け）"},
    ],
    "UNKNOWN": [
        {"cmd": "journalctl -u {service} --since '15 min ago' | tail -n 100", "note": "前後のログを確認して再度解析にかける"},
    ],
}

_EXCEPTION_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Fault))\b")
_PY_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)')
_JAVA_FRAME_RE = re.compile(r"at ([\w.$]+)\(([\w.]+):(\d+)\)")


def analyze_stacktrace(log_content: str) -> dict:
    """エラーログ・スタックトレースを解析し、エラー種別・重大度・原因・発生箇所を返す。

    障害ログやエラーメッセージが貼り付けられたら、最初に必ずこのツールで解析すること。

    Args:
        log_content: 貼り付けられたエラーログ・スタックトレースの本文。

    Returns:
        error_type（DISK_FULL / DB_CONNECTION など）、severity、推定原因、例外クラス、発生箇所、根拠となったログ行。
    """
    text = log_content or ""
    lower = text.lower()
    matched_rule = None
    evidence = ""
    for rule in _ERROR_RULES:
        for pat in rule["patterns"]:
            m = re.search(pat, lower)
            if m:
                matched_rule = rule
                line_start = lower.rfind("\n", 0, m.start()) + 1
                line_end = lower.find("\n", m.end())
                evidence = text[line_start: line_end if line_end != -1 else len(text)].strip()[:200]
                break
        if matched_rule:
            break

    exceptions = _EXCEPTION_RE.findall(text)
    frames = [f"{f}:{ln}" for f, ln in _PY_FRAME_RE.findall(text)] + [f"{c} ({f}:{ln})" for c, f, ln in _JAVA_FRAME_RE.findall(text)]
    return {
        "error_type": matched_rule["type"] if matched_rule else "UNKNOWN",
        "severity": matched_rule["severity"] if matched_rule else "INFO",
        "probable_cause": matched_rule["cause"] if matched_rule else "ログから原因を特定できませんでした（前後のログが必要）",
        "exception_class": exceptions[-1] if exceptions else None,
        "location": frames[-1] if frames else None,
        "evidence_line": evidence or None,
        "line_count": len(text.splitlines()),
    }


def recommend_fix_commands(error_type: str, service_name: str = "my-app") -> dict:
    """エラー種別に応じた一次切り分け・復旧コマンドの候補を返す。

    analyze_stacktrace の結果（error_type）を受けて呼び出すこと。

    Args:
        error_type: analyze_stacktrace が返した error_type（例: DISK_FULL, DB_CONNECTION）。
        service_name: 対象サービス名（systemd のユニット名など）。

    Returns:
        実行順に並んだコマンド候補と注意書き。変更を伴う操作には【変更あり】が付く。
    """
    key = (error_type or "").strip().upper()
    commands = _FIX_COMMANDS.get(key, _FIX_COMMANDS["UNKNOWN"])
    service = (service_name or "my-app").strip()
    return {
        "error_type": key if key in _FIX_COMMANDS else "UNKNOWN",
        "service_name": service,
        "commands": [{"cmd": c["cmd"].format(service=service), "note": c["note"]} for c in commands],
        "caution": "【変更あり】のコマンドは、影響範囲を確認し上長の承認を得てから実行してください。",
    }


INSTRUCTION = """あなたは社内の障害一次対応を支援する「社内障害ログ自動解析Bot」です。
1. 利用者がエラーログやスタックトレースを貼り付けたら、必ず analyze_stacktrace を呼び出して解析する。
2. 続けて、解析結果の error_type を使って recommend_fix_commands を呼び出す（サービス名が分かれば service_name に渡す）。
3. 回答では、重大度・推定原因・根拠となったログ行を先に示し、その後に調査・復旧コマンドを実行順に示す。
4. 【変更あり】のコマンドは、実行前に影響範囲の確認と上長承認が必要であることを必ず添える。
5. ツールの結果に無い原因やコマンドを推測で付け足さない。原因が UNKNOWN の場合は、前後のログを追加で貼るよう依頼する。
6. 結果は A2UI カード（重大度と原因のカード、推奨コマンドのカード）で表示する。ボタンは使わない。
"""

root_agent = Agent(
    model=MODEL,
    name="log_analyzer_bot",
    description="貼り付けられた障害ログを解析し、原因と一次切り分けコマンドを提示するエージェント",
    instruction=INSTRUCTION,
    tools=[analyze_stacktrace, recommend_fix_commands],
    after_model_callback=a2ui_callback,
)
