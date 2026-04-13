"""
Reddit AI関連サブレディット分析スクリプト
r/ClaudeAI, r/ChatGPT, r/LocalLLaMA 等からAIトレンドを取得する。
公開JSON API使用（APIキー不要）。

使い方:
    python scripts/fetch_reddit.py
    python scripts/fetch_reddit.py --subreddits ClaudeAI ChatGPT LocalLLaMA
"""
import json
import os
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, REDDIT_SUBREDDITS, ensure_dirs_for_today

def fetch_subreddit_hot(subreddit: str, limit: int = 15) -> list[dict]:
    """サブレディットのhot投稿を取得する（PRAW OAuth → RSS フォールバック）"""
    # PRAW OAuth（認証情報があれば使用）
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    if client_id and client_secret:
        try:
            return _fetch_via_praw(subreddit, limit, client_id, client_secret)
        except Exception as e:
            print(f"  [WARN] PRAW failed for r/{subreddit}: {e}")

    # RSS フォールバック
    return _fetch_via_rss(subreddit, limit)


def _fetch_via_praw(subreddit: str, limit: int, client_id: str, client_secret: str) -> list[dict]:
    """PRAW OAuth でサブレディットのhot投稿を取得する"""
    try:
        import praw
    except ImportError:
        raise ImportError("praw not installed")

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="ai-news-collector:v1.0 (by /u/ai_news_bot)",
        check_for_async=False,
    )
    posts = []
    for submission in reddit.subreddit(subreddit).hot(limit=limit):
        if submission.stickied:
            continue
        posts.append({
            "id": submission.id,
            "title": submission.title,
            "text": (submission.selftext or "")[:500],
            "url": submission.url,
            "score": submission.score,
            "comments": submission.num_comments,
            "author": str(submission.author),
            "created_at": datetime.fromtimestamp(submission.created_utc).isoformat(),
            "subreddit": subreddit,
            "topic": _extract_topic(submission.title),
            "source": "reddit",
        })
    return posts


def _fetch_via_rss(subreddit: str, limit: int) -> list[dict]:
    """RSS経由でサブレディットの投稿を取得する（認証不要）"""
    url = f"https://www.reddit.com/r/{subreddit}/hot/.rss?limit={limit}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    try:
        import feedparser
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        posts = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            posts.append({
                "id": entry.get("id", link)[-12:],
                "title": title,
                "text": "",
                "url": link,
                "score": 0,
                "comments": 0,
                "author": entry.get("author", ""),
                "created_at": entry.get("published", datetime.now().isoformat()),
                "subreddit": subreddit,
                "topic": _extract_topic(title),
                "source": "reddit",
            })
        return posts
    except Exception as e:
        print(f"  [WARN] RSS failed for r/{subreddit}: {e}")
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
