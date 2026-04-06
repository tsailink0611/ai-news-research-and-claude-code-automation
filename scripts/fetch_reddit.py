"""
Reddit AI関連サブレディット分析スクリプト
r/ClaudeAI, r/ChatGPT, r/LocalLLaMA 等からAIトレンドを取得する。
公開JSON API使用（APIキー不要）。

使い方:
    python scripts/fetch_reddit.py
    python scripts/fetch_reddit.py --subreddits ClaudeAI ChatGPT LocalLLaMA
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, REDDIT_SUBREDDITS, ensure_dirs_for_today

REDDIT_BASE = "https://www.reddit.com"
HEADERS = {"User-Agent": "ai-news-collector/1.0"}


def fetch_subreddit_hot(subreddit: str, limit: int = 15) -> list[dict]:
    """サブレディットのhot投稿を取得する"""
    url = f"{REDDIT_BASE}/r/{subreddit}/hot.json?limit={limit}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            posts.append({
                "id": post.get("id", ""),
                "title": post.get("title", ""),
                "text": post.get("selftext", "")[:500],
                "url": post.get("url", ""),
                "score": post.get("score", 0),
                "comments": post.get("num_comments", 0),
                "author": post.get("author", ""),
                "created_at": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                "subreddit": subreddit,
                "topic": _extract_topic(post.get("title", "")),
                "source": "reddit",
            })
        return posts
    except Exception as e:
        print(f"  [WARN] Failed to fetch r/{subreddit}: {e}")
        return []


def _extract_topic(title: str) -> str:
    """タイトルからトピックを推定する"""
    title_lower = title.lower()
    topic_map = {
        "claude": "Claude", "anthropic": "Anthropic",
        "gpt": "GPT", "openai": "OpenAI", "chatgpt": "ChatGPT",
        "gemini": "Gemini", "google": "Google AI",
        "llama": "LLaMA", "mistral": "Mistral", "qwen": "Qwen",
        "deepseek": "DeepSeek", "local llm": "Local LLM",
        "cursor": "Cursor", "copilot": "Copilot",
        "rag": "RAG", "agent": "AI Agents", "mcp": "MCP",
        "fine-tun": "Fine-tuning", "benchmark": "Benchmarks",
    }
    for keyword, topic in topic_map.items():
        if keyword in title_lower:
            return topic
    return "AI General"


def fetch_all(subreddits: list[str] | None = None, limit: int = 15) -> list[dict]:
    """複数サブレディットから一括取得"""
    if subreddits is None:
        subreddits = REDDIT_SUBREDDITS

    all_posts = []
    for sub in subreddits:
        print(f"[REDDIT] Fetching r/{sub}...")
        posts = fetch_subreddit_hot(sub, limit)
        all_posts.extend(posts)
        print(f"  r/{sub}: {len(posts)} posts")

    print(f"[REDDIT] Total: {len(all_posts)} posts from {len(subreddits)} subreddits")
    return all_posts


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "reddit_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(posts),
            "subreddits": list(set(p.get("subreddit", "") for p in posts)),
            "posts": posts,
        }, f, ensure_ascii=False, indent=2)
    print(f"[REDDIT] Raw data saved to {filepath}")
    return filepath


def run(subreddits: list[str] | None = None, limit: int = 15) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = fetch_all(subreddits, limit)
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI news from Reddit")
    parser.add_argument("--subreddits", nargs="+", default=None, help="Subreddits to fetch")
    parser.add_argument("--limit", type=int, default=15, help="Posts per subreddit")
    args = parser.parse_args()
    results = run(args.subreddits, args.limit)
    print(f"\n=== Results: {len(results)} posts ===")
    for p in results[:10]:
        print(f"  [r/{p['subreddit']} {p['score']}pts] {p['title'][:60]}...")
