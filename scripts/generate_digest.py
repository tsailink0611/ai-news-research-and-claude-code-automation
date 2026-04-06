"""
ダイジェスト生成スクリプト
処理済みデータから人間が読みやすいMarkdownダイジェストを生成する

使い方:
    python scripts/generate_digest.py
    python scripts/generate_digest.py --date 2026-04-06
"""
import json
import sys
import shutil
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import PROCESSED_DIR, DAILY_DIR, LATEST_DIR, ensure_dirs_for_today, today_str


def load_processed(date: str) -> dict | None:
    """処理済みデータを読み込む"""
    filepath = PROCESSED_DIR / date / "processed_articles.json"
    if not filepath.exists():
        print(f"[DIGEST] No processed data for {date}")
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_markdown(data: dict) -> str:
    """Markdownダイジェストを生成する"""
    date = data.get("date", today_str())
    items = data.get("items", [])
    topics = data.get("topics", [])
    stats = data.get("stats", {})

    lines = []
    lines.append(f"# AI News Digest - {date}")
    lines.append(f"\n> Generated at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> Sources: {', '.join(stats.get('sources', ['N/A']))}")
    lines.append(f"> Total articles: {stats.get('total_items', 0)}")

    # 主要トピック
    lines.append("\n## 🔥 主要トピック\n")
    for i, topic in enumerate(topics[:8], 1):
        lines.append(f"{i}. **{topic['topic']}** (スコア: {topic['max_score']:.1f}, {topic['count']}件)")
        if topic.get("top_item"):
            lines.append(f"   - {topic['top_item'][:100]}")

    # トップ記事
    lines.append("\n## 📰 注目記事 TOP 10\n")
    for i, item in enumerate(items[:10], 1):
        title = item.get("title") or item.get("text", "")[:80]
        score = item.get("importance_score", 0)
        source = item.get("source", "unknown")
        url = item.get("url", "")

        lines.append(f"### {i}. {title}")
        lines.append(f"- **スコア**: {score:.1f} | **ソース**: {source}")
        if url:
            lines.append(f"- **URL**: {url}")
        keywords = item.get("matched_keywords", [])
        if keywords:
            lines.append(f"- **キーワード**: {', '.join(keywords[:5])}")
        lines.append("")

    # 全記事一覧
    if len(items) > 10:
        lines.append("\n## 📋 全記事一覧\n")
        lines.append("| # | タイトル | スコア | ソース |")
        lines.append("|---|---------|--------|--------|")
        for i, item in enumerate(items, 1):
            title = (item.get("title") or item.get("text", ""))[:60]
            lines.append(f"| {i} | {title} | {item.get('importance_score', 0):.1f} | {item.get('source', '')} |")

    # 要約セクション
    lines.append("\n## 💡 今日のポイント\n")
    lines.append("- 上位トピックを中心にX投稿ドラフトを作成可能")
    lines.append("- `python scripts/generate_x_drafts.py` でドラフト量産")
    lines.append(f"- 全{len(items)}件のデータが保存済み")

    return "\n".join(lines)


def save_digest(markdown: str, date: str) -> tuple[Path, Path]:
    """ダイジェストを保存する（日次 + latest）"""
    # 日次保存
    daily_path = DAILY_DIR / date / "research_digest.md"
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"[DIGEST] Saved daily digest to {daily_path}")

    # latest更新
    latest_path = LATEST_DIR / "latest_digest.md"
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"[DIGEST] Updated latest digest at {latest_path}")

    return daily_path, latest_path


def run(date: str | None = None) -> str | None:
    """メイン実行"""
    if date is None:
        date = ensure_dirs_for_today()

    data = load_processed(date)
    if data is None:
        return None

    markdown = generate_markdown(data)
    save_digest(markdown, date)
    return markdown


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI news digest")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD)")
    args = parser.parse_args()
    result = run(args.date)
    if result:
        print(f"\n{'='*60}")
        print(result[:500])
        print("...")
