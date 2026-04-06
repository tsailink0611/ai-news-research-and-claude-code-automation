# X News Check

## 目的
X(旧Twitter)上のAI関連速報を確認する。現在は仮実装データを使用。

## 入力
- オプション: 検索クエリ（デフォルト: "AI"）
- オプション: 取得件数（デフォルト: 20）

## 出力
- `data/raw/YYYY-MM-DD/x_news_raw.json` にrawデータ保存
- ターミナルに取得結果のサマリを表示

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation
python scripts/fetch_x_news.py
python scripts/fetch_x_news.py --query "Claude AI" --limit 30
```

## 処理フロー
1. X検索API（現在はモック）でAI関連投稿を取得
2. rawデータとしてJSON保存
3. 結果のサマリを表示

## 仮実装箇所
- X APIへの実接続（X_BEARER_TOKEN設定で有効化予定）
- Grok API連携（GROK_API_KEY設定で有効化予定）

## 後続処理
取得後は以下を実行してパイプラインを進める:
```bash
python scripts/process_data.py
python scripts/generate_digest.py
```
