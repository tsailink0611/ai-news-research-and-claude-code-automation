"""
Hacker News 取得スクリプト
AI関連のトップ記事を取得してフィルタリングする

使い方:
    python scripts/fetch_hn.py
    python scripts/fetch_hn.py --limit 50
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

# TODO: 本番ではasyncioやaiohttpで並列取得に切り替える
try:
    import urllib.request
    import urllib.error
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    HN_TOP_STORIES_URL, HN_ITEM_URL, AI_KEYWORDS,
    RAW_DIR, PROCESSED_DIR, ensure_dirs_for_today, today_str
)


def fetch_json(url: str, timeout: int = 10) -> dict | list | None:
    """URLからJSONを取得する"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ai-news-collector/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def fetch_top_story_ids(limit: int = 30) -> list[int]:
    """トップストーリーIDリストを取得する"""
    ids = fetch_json(HN_TOP_STORIES_URL)
    if ids is None:
        print("[INFO] HN APIに接続できません。ダミーデータを使用します。")
        return []
    return ids[:limit]


def fetch_item(item_id: int) -> dict | None:
    """個別アイテムの詳細を取得する"""
    url = HN_ITEM_URL.format(item_id=item_id)
    return fetch_json(url)


def is_ai_related(item: dict) -> bool:
    """AI関連の記事かどうかを判定する"""
    title = (item.get("title") or "").lower()
    url = (item.get("url") or "").lower()
    text = f"{title} {url}"
    return any(kw in text for kw in AI_KEYWORDS)


def fetch_and_filter(limit: int = 50) -> list[dict]:
    """トップ記事を取得しAI関連でフィルタリングする"""
    print(f"[HN] Fetching top {limit} stories...")
    ids = fetch_top_story_ids(limit)

    if not ids:
        return _get_dummy_data()

    articles = []
    for i, sid in enumerate(ids):
        item = fetch_item(sid)
        if item is None:
            continue
        if is_ai_related(item):
            articles.append({
                "id": item.get("id"),
                "title": item.get("title", ""),
                "url": item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}"),
                "score": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "by": item.get("by", ""),
                "time": item.get("time", 0),
                "source": "hackernews",
            })
        if (i + 1) % 10 == 0:
            print(f"  [HN] Processed {i + 1}/{limit} items, found {len(articles)} AI articles")

    print(f"[HN] Found {len(articles)} AI-related articles from {limit} top stories")
    return articles


def _get_dummy_data() -> list[dict]:
    """API接続不可時のダミーデータ"""
    print("[HN] Using dummy data for demonstration")
    now = int(datetime.now().timestamp())
    return [
        {"id": 99001, "title": "Claude 4 Released: A New Era for AI Assistants",
         "url": "https://example.com/claude4", "score": 850, "comments": 423,
         "by": "ai_researcher", "time": now, "source": "hackernews"},
        {"id": 99002, "title": "OpenAI Announces GPT-5 with Advanced Reasoning",
         "url": "https://example.com/gpt5", "score": 720, "comments": 312,
         "by": "tech_insider", "time": now, "source": "hackernews"},
        {"id": 99003, "title": "MCP Protocol Gains Widespread Adoption Among AI Tools",
         "url": "https://example.com/mcp", "score": 540, "comments": 187,
         "by": "dev_tools", "time": now, "source": "hackernews"},
        {"id": 99004, "title": "Anthropic's New Agent Framework Changes How We Build AI Apps",
         "url": "https://example.com/agents", "score": 480, "comments": 156,
         "by": "ml_engineer", "time": now, "source": "hackernews"},
        {"id": 99005, "title": "Dify 1.0: Open Source LLM App Platform Reaches Stable Release",
         "url": "https://example.com/dify", "score": 390, "comments": 98,
         "by": "oss_dev", "time": now, "source": "hackernews"},
        {"id": 99006, "title": "n8n AI Nodes: Automating Workflows with LLMs",
         "url": "https://example.com/n8n-ai", "score": 310, "comments": 76,
         "by": "automation_fan", "time": now, "source": "hackernews"},
        {"id": 99007, "title": "The Rise of AI Coding Agents: Cursor vs Windsurf vs Claude Code",
         "url": "https://example.com/ai-coding", "score": 680, "comments": 245,
         "by": "code_review", "time": now, "source": "hackernews"},
        {"id": 99008, "title": "RAG in Production: Lessons Learned from 100 Deployments",
         "url": "https://example.com/rag", "score": 420, "comments": 134,
         "by": "data_eng", "time": now, "source": "hackernews"},
    ]


def save_raw(articles: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "hn_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": datetime.now().isoformat(), "count": len(articles),
                    "articles": articles}, f, ensure_ascii=False, indent=2)
    print(f"[HN] Raw data saved to {filepath}")
    return filepath


def run(limit: int = 50) -> list[dict]:
    """メイン実行: 取得→フィルタ→保存"""
    date = ensure_dirs_for_today()
    articles = fetch_and_filter(limit)
    if articles:
        save_raw(articles, date)
    return articles


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI news from Hacker News")
    parser.add_argument("--limit", type=int, default=50, help="Number of top stories to check")
    args = parser.parse_args()
    results = run(args.limit)
    print(f"\n=== Results: {len(results)} AI articles found ===")
    for a in results:
        print(f"  [{a['score']}pts] {a['title']}")
