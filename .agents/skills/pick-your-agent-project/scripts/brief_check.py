#!/usr/bin/env python
"""IPP AI研修 T-2: project_brief.md の書式を検査し、HITMAN 提出用のコードブロックを出力する。

使い方（ワークスペースのルートで）:
  python .agents/skills/pick-your-agent-project/scripts/brief_check.py ipp-agent-workspace/project_brief.md

- 書式が正しければ、1行目が [skill:pick-your-agent-project@v1] のコードブロック（企画書の全文付き）を出力する
- 直すべき点があれば一覧を表示して終了コード 1 で終わる（HITMAN に提出しないこと）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_brief import parse_brief  # noqa: E402

MARKER = "[skill:pick-your-agent-project@v1]"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0] if args else "ipp-agent-workspace/project_brief.md")
    if not path.is_file():
        print(f"{path} が見つかりません。", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    if re.search(r"AIza[0-9A-Za-z_\-]{35}|AQ\.[0-9A-Za-z_\-]{30,}", text):
        print("BRIEF_CHECK: FAIL（企画書に API キーのような文字列があります。削除し、そのキーは無効化・再発行してください）")
        return 1
    result = parse_brief(text)
    if not result["ok"]:
        print("BRIEF_CHECK: FAIL（HITMAN にはまだ提出しないでください。受講生と相談して直してください）")
        for e in result["errors"]:
            print(f"- {e}")
        return 1
    print("```markdown")
    print(MARKER)
    print(f"$ python .agents/skills/pick-your-agent-project/scripts/brief_check.py {path.as_posix()}")
    print(f"BRIEF_CHECK: PASS  agent: {result['agent_name']}  features: {len(result['features'])}  "
          f"screens: {len(result['screens'])}  tools: {len(result['tools'])}")
    print(text.rstrip())
    print("```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
