# project_brief.md (自作AIエージェント要件定義)

## 1. アプリ概要
- **エージェント名**: `ipp_wbs_agent`
- **表示名**: WBS＆スケジュール管理Bot
- **解決する課題**: 階層型タスク管理・ガントチャート・日記機能を備えたカレンダー＆日記共有アプリ

## 2. アーキテクチャ構成
- **フレームワーク**: Google ADK (Agent Development Kit) + Python
- **使用モデル**: gemini-3.8-flash（フォールバック: gemini-3.6-flash）
- **UI**: A2UI (Agent-to-UI) v0.8 リッチカード表示 + FastAPI チャットフロントエンド
- **作業ディレクトリ**: `ipp-agent-workspace`
- **使用スキル**:
  - pick-your-agent-project
  - enable-a2ui
  - ipp-agent-smoke-test
  - build-agent-frontend
  - publish-to-github

## 3. 設計ポイント＆機能要件
- 【A2UIカード表示】enable-a2ui の手順どおり A2UI スキーマをシステムプロンプトに入れ、after_model_callback=a2ui_callback を組み込む（ボタン等の操作系は使えない）
- 【関数ツール】ツールは入力（引数）に応じて実際に処理する。固定値を返すダミー実装は T-3 のスモークテストで不合格になる

## 4. 自作関数ツール要件
- `manage_wbs_schedule(action: str, task_name: str, progress: int = 0)`: 
  階層タスクの進捗集計やガントチャート用スケジュール計算を実際に行う自作関数ツール（入力引数に応じて動的に処理し、固定値のダミーは返さない）

## 5. A2UIカード表示仕様
- 応答の末尾にタスク一覧・ガントチャート・日記連携結果をカード/テーブル形式で可視化（ボタン・フォームは配置せず表示専用とする）

## 6. 動作確認方針（T-3 スモークテスト）
- 内容の異なる2つの質問（例: タスク登録・進捗更新と、ガントチャート集計問い合わせ）を送り、入力に応じてツールが呼ばれ結果が動的に変化することを検証
