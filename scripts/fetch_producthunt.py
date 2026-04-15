"""
Product Hunt AI ツール分析スクリプト
Product Hunt API で最新のAIツール・サービスを取得する。
APIキー未設定時はモックデータにフォールバック。

使い方:
    python scripts/fetch_producthunt.py
    python scripts/fetch_producthunt.py --limit 20
"""
import json
import sys
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, PRODUCTHUNT_ACCESS_TOKEN, ensure_dirs_for_today

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"


def fetch_producthunt(limit: int = 20) -> list[dict]:
    """Product Hunt から最新のAIツールを取得する"""
    if not PRODUCTHUNT_ACCESS_TOKEN:
        print("[PH] NOTE: PRODUCTHUNT_ACCESS_TOKEN not set → skipping (no mock fallback)")
        return []

    try:
        return _fetch_via_api(limit)
    except Exception as e:
        print(f"[PH] API error: {e} → skipping (no mock fallback)")
        return []


def _fetch_via_api(limit: int) -> list[dict]:
    """Product Hunt GraphQL API で取得"""
    headers = {
        "Authorization": f"Bearer {PRODUCTHUNT_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    query = """
    query {
        posts(order: VOTES, postedAfter: "%s", first: %d, topic: "artificial-intelligence") {
            edges {
                node {
                    id
                    name
                    tagline
                    description
                    url
                    votesCount
                    commentsCount
                    website
                    createdAt
                    topics {
                        edges {
                            node { name }
                        }
                    }
                }
            }
        }
    }
    """ % (_days_ago(3), limit)

    resp = requests.post(
        PH_GRAPHQL_URL,
        headers=headers,
        json={"query": query},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    posts = []
    for edge in data.get("data", {}).get("posts", {}).get("edges", []):
        node = edge.get("node", {})
        topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]

        posts.append({
            "id": f"ph_{node.get('id', '')}",
            "title": node.get("name", ""),
            "text": f"{node.get('tagline', '')}. {node.get('description', '')[:300]}",
            "url": node.get("url", ""),
            "website": node.get("website", ""),
            "score": node.get("votesCount", 0),
            "likes": node.get("votesCount", 0),
            "comments": node.get("commentsCount", 0),
            "created_at": node.get("createdAt", ""),
            "topics_list": topics,
            "topic": _extract_topic(node.get("name", ""), node.get("tagline", "")),
            "source": "producthunt",
        })

    print(f"[PH] API returned {len(posts)} AI products")
    return posts


def _days_ago(days: int) -> str:
    """N日前のISO日付を返す"""
    dt = datetime.now() - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def _extract_topic(name: str, tagline: str) -> str:
    """製品名からトピックを推定"""
    text = f"{name} {tagline}".lower()
    topic_map = {
        "code": "AI Coding", "coding": "AI Coding",
        "agent": "AI Agents", "chat": "Chatbot",
        "image": "AI Image", "video": "AI Video",
        "write": "AI Writing", "design": "AI Design",
        "search": "AI Search", "voice": "AI Voice",
        "rag": "RAG", "llm": "LLM Tools",
        "automat": "Automation", "workflow": "Workflow",
    }
    for keyword, topic in topic_map.items():
        if keyword in text:
            return topic
    return "AI Tool"


def _get_mock_data() -> list[dict]:
    """モックデータ"""
    now = datetime.now().isoformat()
    return [
        {"id": "ph_001", "title": "AICodeAssist Pro",
         "text": "AI-powered code review and refactoring tool. Integrates with VS Code and JetBrains.",
         "url": "", "score": 890, "likes": 890, "comments": 123, "created_at": now,
         "topic": "AI Coding", "source": "producthunt_mock"},
        {"id": "ph_002", "title": "AgentFlow",
         "text": "Build autonomous AI agents without code. Visual workflow builder for AI automation.",
         "url": "", "score": 720, "likes": 720, "comments": 98, "created_at": now,
         "topic": "AI Agents", "source": "producthunt_mock"},
        {"id": "ph_003", "title": "RAGBuilder",
         "text": "Create production-ready RAG pipelines in minutes. Connect any data source to any LLM.",
         "url": "", "score": 560, "likes": 560, "comments": 76, "created_at": now,
         "topic": "RAG", "source": "producthunt_mock"},
        {"id": "ph_004", "title": "VoiceClone Studio",
         "text": "Clone any voice with 30 seconds of audio. Real-time voice changing for streams and calls.",
         "url": "", "score": 480, "likes": 480, "comments": 64, "created_at": now,
         "topic": "AI Voice", "source": "producthunt_mock"},
        {"id": "ph_005", "title": "DesignAI",
         "text": "Turn text descriptions into production-ready UI designs. Figma plugin included.",
         "url": "", "score": 340, "likes": 340, "comments": 45, "created_at": now,
         "topic": "AI Design", "source": "producthunt_mock"},
    ]


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "producthunt_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(posts),
            "posts": posts,
        }, f, ensure_ascii=False, indent=2)
    print(f"[PH] Raw data saved to {filepath}")
    return filepath


def run(limit: int = 20) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = fetch_producthunt(limit)
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI products from Product Hunt")
    parser.add_argument("--limit", type=int, default=20, help="Max products")
    args = parser.parse_args()
    results = run(args.limit)
    print(f"\n=== Results: {len(results)} products ===")
    for p in results:
        print(f"  [{p['score']} votes] {p['title']}: {p['text'][:50]}...")
