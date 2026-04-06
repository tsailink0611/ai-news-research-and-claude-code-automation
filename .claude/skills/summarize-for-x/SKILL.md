# Summarize for X

## 目的
保存済みのダイジェストや重要トピックをX向けに短文化する。
1トピックにつき複数の切り口（スタイル）でドラフトを生成する。

## 入力
- `data/processed/YYYY-MM-DD/processed_articles.json` の処理済みデータ

## 出力
- `outputs/daily/YYYY-MM-DD/x_summaries.json` - 全スタイルの要約

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation
python scripts/summarize_for_x.py
python scripts/summarize_for_x.py --date 2026-04-06
```

## 対応スタイル
| スタイル | 説明 |
|---------|------|
| 速報型 | 速報・最新ニュースを端的に伝える |
| 解説型 | 背景や仕組みをわかりやすく解説 |
| 比較型 | ツールや技術を比較して示す |
| 意見型 | 考察や見解を述べる |
| 初心者向け整理型 | 初心者でもわかるように整理 |
| 実務活用示唆型 | 実務でどう使えるかを示す |

## 後続処理
```bash
python scripts/generate_x_drafts.py
```
