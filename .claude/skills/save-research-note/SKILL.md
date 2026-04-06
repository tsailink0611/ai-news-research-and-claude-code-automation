# Save Research Note

## 目的
調査結果をMarkdownとJSONで統一的に保存する。日別保存とlatest更新を行う。

## 入力
- 処理済みデータ（process_data.pyの出力）

## 出力
- `outputs/daily/YYYY-MM-DD/research_digest.md` - 日次ダイジェスト
- `outputs/latest/latest_digest.md` - 最新コピー

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation
python scripts/generate_digest.py
python scripts/generate_digest.py --date 2026-04-06
```

## 処理フロー
1. `data/processed/YYYY-MM-DD/processed_articles.json` を読み込み
2. 主要トピック・注目記事・全記事一覧をMarkdownに整形
3. 日次ディレクトリに保存
4. `outputs/latest/` を最新版で更新

## ファイル命名規則
- raw: `data/raw/YYYY-MM-DD/{source}_raw.json`
- processed: `data/processed/YYYY-MM-DD/processed_articles.json`
- digest: `outputs/daily/YYYY-MM-DD/research_digest.md`
- latest: `outputs/latest/latest_digest.md`

## 前提
`python scripts/process_data.py` を先に実行しておくこと。
