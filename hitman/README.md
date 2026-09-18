# HITMAN: SOP Navigation & AI Pair Operator Cockpit

**開発・設計**: 鈴木 駿平 (Shunpei Suzuki) <suzuki.shunpei@ipp.local>  
**所属**: IPP (IPP)  
**Copyright**: (c) 2026 Shunpei Suzuki (IPP) All Rights Reserved.  
**本番稼働 URL (Cloud Run)**: [https://ipp-hitman-cockpit-1070367799384.us-central1.run.app](https://ipp-hitman-cockpit-1070367799384.us-central1.run.app)

---

## 🎯 プロジェクト概要

**HITMAN** は、ミッションクリティカルなシステム移行・夜間リリース作業において、ヒューマンエラーによるシステム障害（コマンド誤投入、WHERE句欠落による全件更新、確認漏れ）を技術的に防ぐ **AIペアオペレーター・コックピット** です。

従来の「手順書を人間が目視で読み、手動でコマンドをコピペし、手作業でログを確認する」運用を刷新し、**Google ADK (Agent Development Kit)** と **Gemini 3.6 Flash** の推論能力を統合。左右2画面の専用コックピットを通じて、安全かつ客観的なリリース作業を実現します。


---

## 🌟 主要機能

1. **既存手順書の動的インポート (SOP Importer)**:
   - 社内の既存手順書（Excelシートの表セルコピー/TSV、Markdown表、CSV、JSON）を直接貼り付けまたはファイルアップロードするだけで、コマンド、期待結果ログ、注意事項を自律抽出して監視対象手順書を即座に動的更新。
2. **AI有識者 (確認者) による自律Wチェック判定エンジン**:
   - 従来の「作業者＆有識者確認者」による2名体制のWチェックをAIエージェントが自律代行。実行ログを解析し、以下の4状態を自律判定：
     - `VERIFIED_APPROVED` (承認済 ✓): 期待ログとの完全合致を検証し、次手順への進行を正式承認。
     - `BRANCH_ROLLBACK` (自律ロールバック発動 🚨): Segmentation fault 等の致命的障害を検知し、独断投入を遮断して旧環境復旧(R-1)へ自律分岐。
     - `BRANCH_ESCALATION` (自律エスカレーション発動 ⚡): ロック競合やデッドロックを検知し、ゲート(E-1)へ自律分岐して有識者協議を要求。
     - `BLOCKED_RETRY` (再投入ブロック ✕): 容量枯渇やログ不一致時にコマンドの再実行を要求。
3. **厳格なステップ順序制御（Anti-Skip Gate）**:
   - 手順のスキップを厳密に遮断。直前ステップのログ検証（SUCCESS）なしに後続手順を実行させません。
4. **事前確認（Pre-check）の強制**:
   - ディスク空き容量確認（df -h）や事前SELECTなどの事前確認を完了するまで、本番コマンドの実行を許可しません。
5. **SQL影響事前評価エンジン (analyze_sql_impact)**:
   - 投入予定SQLの対象テーブル、更新カラム、WHERE句の安全性、事前SELECT結果との整合性をAIが事前突き合わせ評価。
6. **客観的判断根拠を要求するエスカレーション・ゲート (evaluate_escalation_gate)**:
   - 異常発生時、協議結果・GO/NOGO・客観的判断根拠（こんきょ）の入力がない限り作業再開を遮断。GO判定時は作業リーダー承認のもと【特別モード（2人体制）】へ移行。
7. **最終評価完了報告書 (generate_final_report)**:
   - 作業前後の状態（Before/After）、所要時間、保全成果物（バックアップ、SQL、ログ）をまとめた完了報告書を自動生成。
8. **長期記憶（Memory Bank）**:
   - PreloadMemoryTool とセッション保存コールバックにより、過去の作業履歴やオペレーターの傾向をセッション間で永続保持。
9. **RAGナレッジ検索 (consult_sop_knowledge)**:
   - ディスク枯渇、DBデッドロック、500エラー等のトラブルシューティングナレッジをプレーン関数ツール経由で即時検索。
10. **2画面 Web Cockpit (FastAPI + A2UI)**:
    - 左ペイン: AI対話チャット & A2UIリッチカード & Wチェック判定証バナー
    - 右ペイン: 手順進捗ステータス、SQL影響評価フォーム、エスカレ解除ゲート、最終評価レポート、SOPインポートモーダル

---

## 🏗️ アーキテクチャ

`
[Web Browser]
      │
      ▼ (HTTPS: https://ipp-hitman-cockpit-1070367799384.us-central1.run.app)
┌─────────────────────────────────────────────────────────────┐
│ Cloud Run Container (FastAPI + Static Cockpit UI)           │
│  ├─ / : 2画面操作コックピット (static/index.html)            │
│  ├─ /chat : A2UI レンダラー対応 AI 対話エンドポイント        │
│  └─ /api/* : SOP進捗、SQL評価、エスカレ、最終レポートAPI    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼ (ADK Runner)
┌─────────────────────────────────────────────────────────────┐
│ HITMAN ADK Agent (app/agent.py)                             │
│  ├─ Gemini 3.6 Flash (Client / Vertex AI Express Mode)      │
│  ├─ 3 Operation Modes (NORMAL / TRAINING / SPECIAL_PAIR)    │
│  ├─ PreloadMemoryTool (Memory Bank 長期記憶)                │
│  ├─ SOP Database (手順書定義)                               │
│  ├─ verify_step_output (ログ自動判定)                       │
│  ├─ analyze_sql_impact (SQL影響事前評価)                    │
│  ├─ evaluate_escalation_gate (ゲート制御)                   │
│  ├─ generate_final_report (完了報告)                        │
│  └─ consult_sop_knowledge (RAG ナレッジ検索)                │
└─────────────────────────────────────────────────────────────┘
`

---

## 🧪 テスト実行

```bash
uv run pytest
```
- 全35件のユニットテストおよび結合テストが自動検証されます（100% 合格）。
- 通常モードのDBリリース検証、エスカレーションゲート、上長スキップ、および研修モードのコースA/B動的分岐・T-1〜T-6客観ログ検証を網羅。

---

## 🎓 研修モード（TRAINING）の動的コース分岐
研修モード選択時、左ペインの手順書フローが受講生別のカリキュラム（ステップ T-1 〜 T-6）に動的差し替えされます：
- **【コースA】オリジナルAIツール開発コース**: スキル `pick-your-agent-project` を活用し、受講生自身の現場課題を解決する自作エージェントを企画・開発・デプロイ。
- **【コースB】HITMANクローン構築コース**: アイデアが未定の受講生向けに、AIペアオペレーター（手順書パーサー・客観Wチェック・A2UI・エスカレ制御）自身を自作・デプロイ。
- **AntiGravity 連携プロンプト**:
  - モデル選定: `gemini-3.8-flash` を優先選択、未提供・エラー時は `gemini-3.6-flash` へフォールバック。
  - 専用作業フォルダ: `ipp-agent-workspace`（デフォルト）。画面内の `[⚙️ 研修環境設定]` から特定ドライブ（D:\等）や社内規定パスへ自由に変更可能。
  - Python仮想環境: `uv run python`（推奨）のほか、Conda や既存の `.venv` など受講者個別の Python パスへ自由に変更可能。
  - リポジトリクローン: `git clone https://github.com/almlog/altx-ai-training-lab.git` により `.agents/skills/` の研修スキル群を自律習得。
  - 手順カード上の `[📋 AGYプロンプトをコピー]` ボタンからワンクリックでプロンプトを取得可能（設定したパスに自動置換）。

---

## 🚀 ローカル起動

` ash
# 依存関係インストール
uv sync

# フロントエンドコックピット起動 (ポート 3000)
uv run python frontend/main.py
`
ブラウザで http://127.0.0.1:3000 にアクセスすると、ローカル環境でコックピットが利用可能です。

---
**© 2026 Shunpei Suzuki (IPP)**
