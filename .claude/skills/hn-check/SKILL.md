# HN Check

## 目的
Hacker NewsからAI・LLM・開発系のトップ記事を取得しフィルタリングする。

## 入力
- オプション: 取得件数（デフォルト: 50件のトップストーリーをチェック）

## 出力
- `data/raw/YYYY-MM-DD/hn_raw.json` にrawデータ保存
- AI関連記事のみをフィルタリングして返す

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation
python scripts/fetch_hn.py
python scripts/fetch_hn.py --limit 100
```

## 処理フロー
1. HN Firebase APIからトップストーリーIDを取得
2. 各記事の詳細を取得
3. AI関連キーワードでフィルタリング
4. rawデータとして保存

## フィルタリングキーワード
ai, llm, gpt, claude, openai, anthropic, gemini, mistral, llama,
machine learning, deep learning, transformer, mcp, n8n, dify,
cursor, windsurf, claude code, devin 等

## API接続不可時
ダミーデータを自動的に使用してフロー全体を確認可能。

## 後続処理
```bash
python scripts/process_data.py
python scripts/generate_digest.py
```
