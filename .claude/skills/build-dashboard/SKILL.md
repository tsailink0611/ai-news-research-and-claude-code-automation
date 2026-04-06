# Build Dashboard

## 目的
保存済みデータを集約し、ダッシュボードで一覧確認できるようにする。

## 入力
- 各種保存済みデータ（processed, digest, x-drafts）

## 出力
- `dashboard/data/dashboard.json` - ダッシュボード表示用データ
- `dashboard/index.html` で閲覧可能

## 実行方法
```bash
cd ai-news-research-and-claude-code-automation

# データ生成
python scripts/build_dashboard_data.py

# ブラウザで確認（以下のいずれか）
open dashboard/index.html
python -m http.server 8080 --directory dashboard
```

## 表示項目
- 収集記事数
- Xドラフト数
- 保存日数
- 主要トピック一覧
- 注目記事 TOP 10
- X投稿ドラフト候補（クリックでコピー）
- 最新ダイジェストプレビュー
- 保存済み日付一覧

## 更新タイミング
パイプライン実行後に自動更新される。手動更新も可能:
```bash
python scripts/build_dashboard_data.py
```
