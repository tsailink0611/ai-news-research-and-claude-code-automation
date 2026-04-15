"""
X(旧Twitter) ブックマーク取得スクリプト
X API v2 を使って自分のブックマークからAI関連投稿を取得する。
APIキー未設定時はモックデータにフォールバック。

使い方:
    python scripts/fetch_x_bookmarks.py
    python scripts/fetch_x_bookmarks.py --limit 50
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, X_BEARER_TOKEN, AI_KEYWORDS, ensure_dirs_for_today

X_API_BASE = "https://api.twitter.com/2"


def fetch_bookmarks(limit: int = 50) -> list[dict]:
    """Xのブックマークを取得する"""
    if not X_BEARER_TOKEN:
        print("[X-BOOKMARKS] NOTE: X_BEARER_TOKEN not set → skipping (no mock fallback)")
        return []

    try:
        return _fetch_via_api(limit)
    except Exception as e:
        print(f"[X-BOOKMARKS] API error: {e} → skipping (no mock fallback)")
        return []


def _fetch_via_api(limit: int) -> list[dict]:
    """X API v2 でブックマークを取得"""
    headers = {
        "Authorization": f"Bearer {X_BEARER_TOKEN}",
    }

    # まず自分のユーザーIDを取得
    me_resp = requests.get(f"{X_API_BASE}/users/me", headers=headers, timeout=15)
    me_resp.raise_for_status()
    user_id = me_resp.json()["data"]["id"]

    # ブックマーク取得
    params = {
        "max_results": min(limit, 100),
        "tweet.fields": "created_at,public_metrics,entities",
        "expansions": "author_id",
        "user.fields": "username",
    }
    resp = requests.get(
        f"{X_API_BASE}/users/{user_id}/bookmarks",
        headers=headers, params=params, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # ユーザー情報のマッピング
    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

    posts = []
    for tweet in data.get("data", []):
        text = tweet.get("text", "")

        # AI関連フィルタリング
        if not _is_ai_related(text):
            continue

        author_id = tweet.get("author_id", "")
        author = users.get(author_id, {})
        metrics = tweet.get("public_metrics", {})

        posts.append({
            "id": tweet.get("id", ""),
            "text": text,
            "author": f"@{author.get('username', 'unknown')}",
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "comments": metrics.get("reply_count", 0),
            "score": (metrics.get("like_count", 0) + metrics.get("retweet_count", 0) * 2) // 10,
            "created_at": tweet.get("created_at", ""),
            "url": f"https://x.com/i/web/status/{tweet.get('id', '')}",
            "topic": _extract_topic(text),
            "source": "x_bookmarks",
        })

    print(f"[X-BOOKMARKS] Fetched {len(posts)} AI-related bookmarks")
    return posts


def _is_ai_related(text: str) -> bool:
    """AI関連かどうか判定"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in AI_KEYWORDS)


def _extract_topic(text: str) -> str:
    """テキストからトピックを推定"""
    text_lower = text.lower()
    topic_map = {
        "claude": "Claude", "anthropic": "Anthropic",
        "gpt": "GPT", "openai": "OpenAI",
        "gemini": "Gemini", "llama": "LLaMA",
        "cursor": "Cursor", "windsurf": "Windsurf",
        "mcp": "MCP", "agent": "AI Agents",
        "rag": "RAG", "fine-tun": "Fine-tuning",
        "deepseek": "DeepSeek", "dify": "Dify",
    }
    for keyword, topic in topic_map.items():
        if keyword in text_lower:
            return topic
    return "AI General"


def _get_mock_data() -> list[dict]:
    """モックデータ"""
    now = datetime.now().isoformat()
    return [
        {"id": "bm_001", "text": "Claude Codeのスキル機能が便利すぎる。プロジェクトごとにカスタムコマンドを定義できるの最高。",
         "author": "@ai_dev_jp", "likes": 234, "retweets": 56, "comments": 12,
         "score": 34, "created_at": now, "topic": "Claude", "source": "x_bookmarks_mock"},
        {"id": "bm_002", "text": "MCPサーバーの自作方法をまとめた。TypeScriptで書けるので意外と簡単。GitHub連携が捗る。",
         "author": "@mcp_builder", "likes": 456, "retweets": 123, "comments": 34,
         "score": 70, "created_at": now, "topic": "MCP", "source": "x_bookmarks_mock"},
        {"id": "bm_003", "text": "ローカルLLM比較：Qwen3-8BがGPT-3.5を完全に超えた。しかもM1 Macで動く。時代変わったな。",
         "author": "@local_llm_fan", "likes": 678, "retweets": 189, "comments": 45,
         "score": 105, "created_at": now, "topic": "Local LLM", "source": "x_bookmarks_mock"},
        {"id": "bm_004", "text": "RAGの精度を上げるコツ：チャンキングサイズは512トークンがベスト。重複率20%でリコール向上。",
         "author": "@rag_tips", "likes": 345, "retweets": 89, "comments": 23,
         "score": 52, "created_at": now, "topic": "RAG", "source": "x_bookmarks_mock"},
        {"id": "bm_005", "text": "Dify + n8n の組み合わせが最強。ノーコードでAIワークフロー自動化。月額$0で運用可能。",
         "author": "@nocode_ai", "likes": 567, "retweets": 145, "comments": 56,
         "score": 85, "created_at": now, "topic": "Dify", "source": "x_bookmarks_mock"},
    ]


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "x_bookmarks_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(posts),
            "posts": posts,
        }, f, ensure_ascii=False, indent=2)
    print(f"[X-BOOKMARKS] Raw data saved to {filepath}")
    return filepath


def run(limit: int = 50) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = fetch_bookmarks(limit)
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI bookmarks from X")
    parser.add_argument("--limit", type=int, default=50, help="Max bookmarks")
    args = parser.parse_args()
    results = run(args.limit)
    print(f"\n=== Results: {len(results)} bookmarks ===")
    for p in results:
        print(f"  [{p['likes']}♥] {p['text'][:60]}...")
