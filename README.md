# AI News Research & Claude Code Automation

AIニュース収集 → 保存 → 可視化 → 再要約 → X投稿ドラフト量産 までを一気通貫で行う基盤プロジェクト。

## 目的

1. AIニュースを収集する（Hacker News, X等）
2. 調査結果を構造化して保存する
3. ダッシュボードに集約して確認する
4. 重要トピックを再要約する
5. X投稿向けドラフトに変換する
6. 20〜30本の発信用ドラフトを量産する

## クイックスタート

```bash
cd ai-news-research-and-claude-code-automation

# パイプライン一括実行（収集→処理→ダイジェスト→要約→ドラフト→ダッシュボード）
python scripts/run_pipeline.py

# ダッシュボード確認
open dashboard/index.html
# または
python -m http.server 8080 --directory dashboard
```

## どこを見ればいいか

| 目的 | 場所 |
|------|------|
| **最初に見る** | `dashboard/index.html` |
| **最新ダイジェスト** | `outputs/latest/latest_digest.md` |
| **最新Xドラフト** | `outputs/latest/latest_x_drafts.md` |
| **日次詳細** | `outputs/daily/YYYY-MM-DD/` |
| **Xドラフト詳細** | `outputs/x-drafts/YYYY-MM-DD/` |
| **生データ** | `data/raw/YYYY-MM-DD/` |

## 実行コマンド一覧

### パイプライン

```bash
# 全ステップ一括実行
python scripts/run_pipeline.py

# 個別ステップ
python scripts/run_pipeline.py --step fetch      # データ収集のみ
python scripts/run_pipeline.py --step process    # データ処理のみ
python scripts/run_pipeline.py --step digest     # ダイジェスト生成のみ
python scripts/run_pipeline.py --step summarize  # X向け再要約のみ
python scripts/run_pipeline.py --step drafts     # Xドラフト生成のみ
python scripts/run_pipeline.py --step dashboard  # ダッシュボード更新のみ
```

### 個別スクリプト

```bash
python scripts/fetch_hn.py              # Hacker News取得
python scripts/fetch_hn.py --limit 100  # 取得件数指定

python scripts/fetch_x_news.py          # X速報確認（現在モック）
python scripts/fetch_x_news.py --query "Claude AI"

python scripts/process_data.py           # データ処理・スコアリング
python scripts/generate_digest.py        # Markdownダイジェスト生成
python scripts/summarize_for_x.py        # X向け再要約
python scripts/generate_x_drafts.py      # Xドラフト量産
python scripts/generate_x_drafts.py --count 25

python scripts/build_dashboard_data.py   # ダッシュボードデータ更新
```

## ダッシュボード確認方法

`dashboard/index.html` をブラウザで開く。表示項目:

- 収集記事数・Xドラフト数・保存日数
- 主要トピック一覧（スコア付き）
- 注目記事 TOP 10
- X投稿ドラフト候補（クリックでコピー可）
- 最新ダイジェストプレビュー
- 保存済み日付一覧

> JSONを読み込むため、ローカルサーバー経由で開くことを推奨:
> `python -m http.server 8080 --directory dashboard`

## Xドラフト確認方法

- `outputs/latest/latest_x_drafts.md` で最新ドラフト一覧を確認
- 各ドラフトにはメタ情報（トピック、スタイル、緊急度、推奨用途）付き
- コードブロック内のテキストをそのままコピペ可能
- ダッシュボードではクリックでクリップボードにコピー

### ドラフトスタイル

| スタイル | 用途 |
|---------|------|
| 速報型 | 最新ニュースを端的に伝える |
| 解説型 | 背景や仕組みをわかりやすく解説 |
| 比較型 | ツールや技術の比較 |
| 意見型 | 考察や見解 |
| 初心者向け整理型 | 初心者向けの整理 |
| 実務活用示唆型 | 実務での活用方法 |

## ディレクトリ構成

```
ai-news-research-and-claude-code-automation/
├── .claude/skills/         # Claude Code project skills
│   ├── x-news-check/
│   ├── hn-check/
│   ├── save-research-note/
│   ├── build-dashboard/
│   ├── summarize-for-x/
│   └── generate-x-drafts/
├── scripts/                # 実行スクリプト群
│   ├── config.py           # 共通設定
│   ├── fetch_hn.py         # HN取得
│   ├── fetch_x_news.py     # X速報取得（モック）
│   ├── process_data.py     # データ処理
│   ├── generate_digest.py  # ダイジェスト生成
│   ├── summarize_for_x.py  # X向け再要約
│   ├── generate_x_drafts.py # Xドラフト量産
│   ├── build_dashboard_data.py # ダッシュボードデータ
│   └── run_pipeline.py     # パイプライン一括実行
├── data/
│   ├── raw/                # 取得した元データ
│   └── processed/          # 整形済みデータ
├── outputs/
│   ├── daily/              # 日別ダイジェスト
│   ├── latest/             # 最新版（常にここを見る）
│   └── x-drafts/           # X投稿用ドラフト
├── dashboard/
│   ├── index.html          # ダッシュボード
│   └── data/               # ダッシュボード用JSON
├── .env.example
├── .gitignore
└── README.md
```

## データ4層設計

| Layer | 内容 | 保存先 |
|-------|------|--------|
| raw | 取得した元データ | `data/raw/YYYY-MM-DD/` |
| processed | 整形済みJSON | `data/processed/YYYY-MM-DD/` |
| digest | 人間向け要約 | `outputs/daily/YYYY-MM-DD/` |
| x-drafts | X投稿用ドラフト | `outputs/x-drafts/YYYY-MM-DD/` |

## 現在の実装状態

### 実装済み
- ✅ Hacker News API取得（実API接続 + フォールバック）
- ✅ データ処理・スコアリング・重複排除
- ✅ Markdownダイジェスト生成
- ✅ X向け6スタイル再要約
- ✅ Xドラフト20〜30本量産
- ✅ ダッシュボード（静的HTML）
- ✅ パイプライン一括実行
- ✅ Claude Code project skills（6種）
- ✅ 日次保存 + latest自動更新

### 仮実装（TODO）
- ⬜ X(Twitter) API実接続 → `X_BEARER_TOKEN` 設定で有効化
- ⬜ Grok API連携 → `GROK_API_KEY` 設定で有効化
- ⬜ Claude APIによる高品質要約 → `ANTHROPIC_API_KEY` 設定で有効化
- ⬜ 非同期並列取得（asyncio化）

## 今後の拡張候補

| 拡張 | 概要 | 優先度 |
|------|------|--------|
| **Grok API** | X上のリアルタイムAI情報検索 | 高 |
| **YouTube字幕取得** | AI系YouTube動画の要約 | 中 |
| **Google Trends** | AIトレンドの定量把握 | 中 |
| **Product Hunt** | 新規AIツールの発見 | 中 |
| **SerpApi** | Google検索結果の取得 | 中 |
| **Reddit** | r/MachineLearning等の取得 | 中 |
| **中国SNS** | 中国AI動向の把握 | 低 |
| **Notion連携** | データのNotion自動保存 | 低 |
| **n8n** | ワークフロー自動化 | 低 |
| **MCP** | Claude連携の強化 | 中 |

## 拡張方針

1. 新しいソースは `scripts/fetch_{source}.py` として追加
2. `config.py` にAPI設定を追加
3. `process_data.py` の `load_raw_data` が自動認識
4. パイプラインに組み込み
5. ダッシュボードは `dashboard.json` 経由で自動反映

外部APIは環境変数で管理し、未設定時はモックデータにフォールバックする設計。
