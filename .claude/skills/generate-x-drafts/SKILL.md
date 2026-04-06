# Generate X Drafts

## 目的
保存済みデータをもとにX投稿ドラフトを20〜30本量産する。

## 入力
- `outputs/daily/YYYY-MM-DD/x_summaries.json` または処理済みデータ
- オプション: 生成件数（デフォルト: 30本）

## 出力
- `outputs/x-drafts/YYYY-MM-DD/x_drafts.json` - ドラフト一覧（JSON）
- `outputs/x-drafts/YYYY-MM-DD/x_drafts.md` - ドラフト一覧（Markdown）
- `outputs/latest/latest_x_drafts.md` - 最新版
- `outputs/latest/latest_x_drafts.json` - 最新版（JSON）

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation
python scripts/generate_x_drafts.py
python scripts/generate_x_drafts.py --date 2026-04-06 --count 25
```

## ドラフトのメタ情報
各ドラフトには以下の情報が付与される:
- **topic**: トピック名
- **source_type**: ソース種別
- **style**: スタイル（速報/解説/比較/意見/初心者向け/実務活用）
- **urgency**: 緊急度（high/medium/low）
- **recommended_use**: 推奨用途

## コピペ方法
- Markdownファイルのコードブロック内がそのままコピペ可能
- ダッシュボードではクリックでクリップボードにコピー

## パイプライン一括実行
```bash
python scripts/run_pipeline.py
```
