# IPP 社内AI実践研修カリキュラム
## 〜 HITMAN（AIペアオペレーター）とアンチグラビティで拓く、自律型AIエージェント開発・デプロイ実践 〜

**開発・監修**: IPP 鈴木 駿平 (Shunpei Suzuki) <suzuki.shunpei@ipp.local>  
**著作権**: Copyright (c) 2026 Shunpei Suzuki (IPP) All Rights Reserved.  
**プロジェクト名**: `ipp-ai-training-lab`  
**HITMAN 稼働エンジン**: `gemini-3.6-flash` (Vertex AI / Global)  
**公式プラットフォーム URL**: [https://ipp-hitman-cockpit-1070367799384.us-central1.run.app](https://ipp-hitman-cockpit-1070367799384.us-central1.run.app)  
**公式ハンズオンマニュアル（完全版）**: [`TRAINING_LAB_MANUAL.md`](./TRAINING_LAB_MANUAL.md)

---

## 1. 研修の目的と受講生のゴール

本研修の目的は、**「全員が同じHITMANをゼロから作ること」ではありません**。

受講生は、鈴木 駿平（IPP）が設計・開発した公式AIペアオペレーター**「HITMAN」**をオペレーション基盤として活用し、HITMANから提供される検証済み手順・プロンプトを**「アンチグラビティ（Antigravity）」**に投入します。

アンチグラビティは裏側に配備された高度な**Skills（AIガバナンス研修 M0〜M5、開発・デプロイスキル）**を自律的に活用し、受講者を強力に伴走します。受講生はセキュリティやガバナンスの勘所を実体験した上で、**「自分自身の現場課題を解決する、思い思いのオリジナルAIエージェントやツール」**を企画・開発し、Cloud Runへの本番デプロイまでを達成します。

```text
┌─────────────────────────────────────────────────────────────┐
│ 【Step 1】HITMAN Cockpit（Cloud Run稼働中 / gemini-3.6-flash）│
│  ・受講生はブラウザからアクセスする（開発不要・完成版）     │
│  ・Excel手順書（.xlsm）やSOPを読み込み、手順をナビゲート    │
│  ・安全に検証された「アンチグラビティ用プロンプト」を生成   │
└──────────────────────────────┬──────────────────────────────┘
                               │ プロンプトをコピー＆ペースト
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 【Step 2】アンチグラビティ（Antigravity / agy）              │
│  ・受講生自身のPC上で動作するAIペアプログラミング環境       │
│  ・受講生個人の有料APIキー（Vertex AI / Gemini API）で駆動  │
└──────────────────────────────┬──────────────────────────────┘
                               │ 裏側でSkillsを自律読み込み
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 【Step 3】リポジトリ内 Skills（.agents/skills/）             │
│  ・M0〜M5 ガバナンス＆セキュリティ検証（IAM・Model Armor等） │
│  ・独自エージェント企画（pick-your-agent-project）           │
│  ・フロントエンド、A2UI、RAG、メモリバンク、デプロイスキル │
└──────────────────────────────┬──────────────────────────────┘
                               │ 高度な開発技術を体得
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 【Goal】受講生各自が思い思いのAIツールを開発＆Cloud Run公開 │
│  ・社内問い合わせボット、ログ分析ツール、コード監査AIなど   │
│  ・各自が企画・実装したコンテナを自分のCloud Runへデプロイ   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 受講者環境の前提条件と事前準備ガイド

> [!IMPORTANT]
> **研修用Googleアカウント・開発PCの配布はありません（受講前日までに準備必須）**  
> 本研修では、受講生各自が **個人のPC環境** および **個人のGoogleアカウント（`@gmail.com` 等）** を使用し、自身の Google Cloud プロジェクトを作成して **有料APIキー（Vertex AI Express Mode / Gemini APIキー）を自前で払い出して** 受講します。
> 
> 詳細なセットアップ手順、最低限求められるスキル、PC環境要件、およびセルフチェックコマンドについては、以下の専用ドキュメントを必ず確認し、受講前日までに完了させてください：  
> 👉 **[`PREREQUISITES.md`（受講者 事前準備・前提スキル・PC環境ガイド）](./PREREQUISITES.md)**

### 【最低受講条件（4大必須要件）】
1. **個人Googleアカウントの所持**（`@gmail.com` 等）
2. **有料APIキーの発行**（クレジットカード紐付け、または事前入金の請求先アカウント設定）
3. **アンチグラビティ（Google AntiGravity / agy）のインストールとログイン認証**
4. **Python（3.11 または 3.12+）のインストールおよびターミナルでの実行確認**

### 【事前準備における作業環境・パスの個別最適化（任意）】
受講生各自の PC 環境（ドライブ容量、会社セキュリティ規程、既存の仮想環境）に柔軟に適応するため、HITMAN は作業環境の完全個別設定に対応しています：
- **作業フォルダの自由選択**: デフォルト（`ipp-agent-workspace`）以外に、容量に余裕のある別ドライブ（例: `D:\dev\lab`）や社内標準ディレクトリ（例: `C:\workspace\`）、Mac/Linuxのホーム配下などを自由に事前決定できます。
- **Python仮想環境の自由指定**: 高速パッケージマネージャー `uv`（推奨）のほか、社内業務ですでに構築済みの Conda 環境（`conda run -n py312 python`）や既存の `.venv` をそのまま活用できます。
- **HITMAN での事前反映**: 研修当日、HITMAN Cockpit の **`[⚙️ 研修環境設定]`** に入力するだけで、全ステップ（T-1〜T-6）のプロンプト・コマンド・合否判定が受講生個別のパスへ一瞬で連動します。

---

## 3. 実践ハンズオン・ステップ（全10マイルストーン）

### 【マイルストーン 1】個人GCPプロジェクトの作成と課金（Billing）の有効化
※ 初心者が最もつまずきやすい最重要ステップです！

1. [Google Cloud Console](https://console.cloud.google.com/) に個人の Google アカウントでログイン。
2. 画面上部のプロジェクト選択から **「新しいプロジェクト」** を作成。
   - プロジェクト名: `ipp-ai-training-<自分の名前>`（例: `ipp-ai-training-tanaka`）
3. **お支払い（Billing）の紐付け（必須）**:
   - メニューから「お支払い（Billing）」を開き、有効なクレジットカードまたは無料トライアル枠をプロジェクトに紐付ける。
   - **注意**: 課金が未設定のプロジェクトでは Vertex AI の推論および Cloud Run のビルドが 403 Forbidden で遮断されます。

### 【マイルストーン 2】個人有料APIキーの発行と種別の理解

1. **APIキーの発行手順**:
   - **Vertex AI Express Mode キー（推奨）**: Google Cloud Console の [Vertex AI Studio] ➡️ [API キー] より作成。キーの先頭が `AQ.` で始まる高信頼キーです。
   - **AI Studio キー**: [Google AI Studio (aistudio.google.com)] より発行。キーの先頭が `AIza...` で始まるキーです。
2. 取得した個人キーを、ローカル環境の `.env` または環境変数に設定します：
   ```bash
   GOOGLE_API_KEY=AQ.xxxx...（あなたの個人キー）
   GOOGLE_CLOUD_PROJECT=ipp-ai-training-xxxx
   GOOGLE_CLOUD_LOCATION=global
   GOOGLE_GENAI_USE_VERTEXAI=true
   ```

### 【マイルストーン 3】クラウド必須APIの有効化

Cloud Shell またはローカルの gcloud CLI にて以下のコマンドを実行し、必要な API を一括有効化します：

```bash
# Google Cloud CLI へのログイン（個人アカウント）
gcloud auth login

# プロジェクトの設定
gcloud config set project ipp-ai-training-xxxx

# 必須APIの有効化
gcloud services enable \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

### 【マイルストーン 4】HITMAN Cockpit を操作しプロンプトを取得する

1. 鈴木 駿平がデプロイした **HITMAN Cockpit**（`https://ipp-hitman-cockpit-1070367799384.us-central1.run.app`）をブラウザで開く。
2. 現場実務用Excel手順書（`.xlsm`）をアップロード、またはプリセットのSOP手順を選択（研修生は「🎓 研修モード」を選択）。
3. 作業フォルダや仮想環境を独自指定したい場合は、画面内の **`[⚙️ 研修環境設定]`** から自由にパスを調整（指定がない場合は標準の `ipp-agent-workspace` が自動適用）。
4. 画面に表示される **「安全チェック」「パラメータ置換」「Wチェック承認」** を確認。
5. HITMAN が提示する **「アンチグラビティに投入する検証済みプロンプト」** をコピーする。

### 【マイルストーン 5】アンチグラビティへのプロンプト投入と裏側SKILLの体感

1. 受講生のPCで **アンチグラビティ（Antigravity）** を起動。
2. HITMAN からコピーしたプロンプトを投入する。
3. アンチグラビティが裏側の **AIガバナンス研修スキル（`novasmart-governance-lab`）** を自律的に読み込み、以下のタスクを実行する様を観察する：
   - **M0（すべてを見る）**: カタログにないシャドウエージェントや共有ログインの検知。
   - **M1（アクションを起こす）**: 専用サービスアカウントの分離と最小権限化（IAM適正化）。
   - **M2（接続の制御）**: リソースレベル IAM による不正呼び出し遮断（200 ➡️ 403）。
   - **M3（コンテンツ保護）**: Model Armor によるインジェクション攻撃の防御。
   - **M5（評価と採点）**: 客観的スコアカードによる品質判定。

### 【マイルストーン 6】思い思いのツールを企画する（`pick-your-agent-project`）

受講生は全員同じツールを作るのではなく、アンチグラビティの支援を受けながら **「自分の業務で本当に欲しいツール」** をブレインストーミングします：
- **社内ナレッジ検索・FAQボット**（社内規程や障害マニュアルをRAG検索）
- **SQL・ログ自動分析エージェント**（エラーログを読み込み原因と対策を提示）
- **コードレビュー・セキュリティ監査アシスタント**
- **議事録・ドキュメント要約生成ツール**

### 【マイルストーン 7】エージェントコードとフロントエンドの実装

アンチグラビティのコード生成機能を使い、企画したツールの実装を行います：
- **ADK Agent 実装**: `app/agent.py` にGeminiモデル、システムプロンプト、ツール関数を定義。
- **A2UI リッチカード統合**: テキストだけでなく、表やカード形式で綺麗に出力。
- **FastAPI プロキシ**: ブラウザとエージェントをシームレスに中継。

### 【マイルストーン 8】自動テストによる品質保証（Pytest）

テスト駆動で品質を担保するため、自作エージェントの単体テストと結合テストを実行します：
```bash
uv run pytest
```
- 全テストが Green（合格）になることを確認します。

### 【マイルストーン 9】自作ツールの Cloud Run 本番デプロイ

自作したオリジナルAIツールを、受講生個人の GCP プロジェクト上の Cloud Run へデプロイします：

```bash
gcloud run deploy my-custom-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_API_KEY=AQ.xxx,GOOGLE_CLOUD_PROJECT=ipp-ai-training-xxxx,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true"
```

デプロイ完了後に出力される Service URL（`https://my-custom-agent-xxxx.run.app`）をブラウザで開けば、世界中からアクセス可能な受講生独自のAIツールが完成します！

### 【マイルストーン 10】成果物の発表と共有

受講生各自の GitHub アカウントに完成したリポジトリをプッシュし、チーム内で「どんな課題を解決するどんなAIツールを作ったか」のデモ・成果発表を行います。

---

## 4. 講師・研修生向け FAQ & トラブルシューティング

| 症状 / エラー | 原因 | 解決手順 |
|---|---|---|
| **403 PERMISSION_DENIED** | 個人GCPプロジェクトの課金（Billing）が未設定、またはAPIが無効 | Cloud Console の「お支払い」でカード紐付けを確認し、`gcloud services enable` を再実行 |
| **404 NOT_FOUND (Model Garden)** | リージョン指定が誤っている | `gemini-3.6-flash` は `global` リージョンで稼働するため、`GOOGLE_CLOUD_LOCATION=global` を設定 |
| **Antigravity でコマンド実行時に毎回確認が出る** | 権限設定が Review モードになっている | 設定（⚙️）の Agent Settings から **Tool Execution Policy** を **`Always Proceed`**（または Turbo）に変更 |
| **Cloud Build のアップロードが遅い** | `.venv` や不要なファイルがアップロードに含まれている | `.dockerignore` に `.venv/` や `__pycache__/` を追加して除外 |

---
**© 2026 Shunpei Suzuki (IPP)**
