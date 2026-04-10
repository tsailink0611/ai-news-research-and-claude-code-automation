"""
X(旧Twitter) AI速報確認スクリプト
Grok API を使ってリアルタイムのAIニュースを取得する。
APIキー未設定時はモックデータにフォールバック。

使い方:
    python scripts/fetch_x_news.py
    python scripts/fetch_x_news.py --query "Claude AI"
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, AI_KEYWORDS, GROK_API_KEY, GROK_API_BASE, ensure_dirs_for_today


def search_x_news(query: str = "AI", limit: int = 20) -> list[dict]:
    """
    X上のAI関連投稿を検索する。
    Grok APIキーがあれば実データ取得、なければモックデータ。
    """
    print(f"[X-NEWS] Searching for: {query} (limit: {limit})")

    if GROK_API_KEY:
        try:
            return _fetch_via_grok(query, limit)
        except Exception as e:
            print(f"[X-NEWS] Grok API error: {e} → スキップ")
            return []
    else:
        print("[X-NEWS] GROK_API_KEY未設定 → スキップ（モックデータは使用しない）")
        return []


def _fetch_via_grok(query: str, limit: int) -> list[dict]:
    """Grok API (xAI) を使ってAIニュースを取得する"""
    print(f"[X-NEWS] Fetching via Grok API...")

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }

    # Grok にAIニュースの検索・要約を依頼する
    prompt = f"""You are an AI news researcher. Search for the latest AI-related news and discussions on X (Twitter) about: {query}

Return exactly {limit} recent noteworthy posts/topics as a JSON array. Each item should have:
- "id": a unique identifier string
- "text": the post content or topic summary in Japanese (100-200 chars)
- "author": author handle (e.g. @username)
- "likes": estimated engagement (integer)
- "retweets": estimated shares (integer)
- "created_at": ISO timestamp
- "topic": main topic keyword
- "source": "x_grok"

Focus on: AI models, tools, frameworks, industry news, breakthroughs.
Return ONLY the JSON array, no other text."""

    payload = {
        "model": "grok-3-latest",
        "messages": [
            {"role": "system", "content": "You are a helpful AI news researcher. Always respond with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    response = requests.post(
        f"{GROK_API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    content = result["choices"][0]["message"]["content"]

    # JSON部分を抽出（コードブロックで囲まれている場合に対応）
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # 最初の ```json\n を除去
        content = content.rsplit("```", 1)[0]  # 最後の ``` を除去

    posts = json.loads(content)

    # 必須フィールドのバリデーション
    validated = []
    for post in posts:
        validated.append({
            "id": post.get("id", f"grok_{len(validated)}"),
            "text": post.get("text", ""),
            "author": post.get("author", "@unknown"),
            "likes": int(post.get("likes", 0)),
            "retweets": int(post.get("retweets", 0)),
            "created_at": post.get("created_at", datetime.now().isoformat()),
            "topic": post.get("topic", "AI"),
            "source": "x_grok",
        })

    print(f"[X-NEWS] Grok API returned {len(validated)} posts")
    return validated


def _get_mock_x_data(query: str) -> list[dict]:
    """モックデータ生成（API未接続時）"""
    now = datetime.now().isoformat()
    mock_posts = [
        {"id": "x_001", "text": "Claude Code がさらに進化。MCP対応で外部ツール連携が簡単に。開発者の生産性が劇的に変わりそう。",
         "author": "@ai_watcher_jp", "likes": 342, "retweets": 89, "created_at": now,
         "topic": "Claude Code", "source": "x_mock"},
        {"id": "x_002", "text": "GPT-5のリリースが近いとの噂。マルチモーダル強化と推論能力の大幅向上が焦点か。OpenAIの次の一手に注目。",
         "author": "@tech_news_daily", "likes": 567, "retweets": 234, "created_at": now,
         "topic": "GPT-5", "source": "x_mock"},
        {"id": "x_003", "text": "AIコーディングツール比較: Cursor 0.50 vs Windsurf vs Claude Code。それぞれの強みをまとめました。結論→用途次第。",
         "author": "@dev_tools_review", "likes": 891, "retweets": 345, "created_at": now,
         "topic": "AI Coding Tools", "source": "x_mock"},
        {"id": "x_004", "text": "Dify 1.0が正式リリース。ノーコードでRAGアプリが作れる時代。エンジニアじゃなくてもAIアプリ開発が可能に。",
         "author": "@nocode_ai", "likes": 234, "retweets": 67, "created_at": now,
         "topic": "Dify", "source": "x_mock"},
        {"id": "x_005", "text": "n8nのAIノードが革命的。ワークフロー自動化×LLMで、定型業務の80%が自動化できる未来が見えてきた。",
         "author": "@automation_master", "likes": 456, "retweets": 123, "created_at": now,
         "topic": "n8n", "source": "x_mock"},
        {"id": "x_006", "text": "Anthropicが企業向けMCPサーバーの構築ガイドを公開。自社データとClaude連携のベストプラクティスが明確に。",
         "author": "@enterprise_ai", "likes": 178, "retweets": 45, "created_at": now,
         "topic": "MCP", "source": "x_mock"},
        {"id": "x_007", "text": "RAGの実運用で一番大事なのはチャンキング戦略。100社の導入事例から見えたベストプラクティスを共有。",
         "author": "@rag_expert", "likes": 623, "retweets": 189, "created_at": now,
         "topic": "RAG", "source": "x_mock"},
        {"id": "x_008", "text": "AI Agent 時代の到来。単なるチャットボットから、自律的にタスクを遂行するAIへ。2025年後半の主戦場はここ。",
         "author": "@future_tech", "likes": 789, "retweets": 267, "created_at": now,
         "topic": "AI Agents", "source": "x_mock"},
        {"id": "x_009", "text": "Google Gemini 2.5 Proの推論能力がすごい。数学・コーディング系タスクでGPT-4oを上回るベンチマーク結果。",
         "author": "@benchmark_lab", "likes": 345, "retweets": 98, "created_at": now,
         "topic": "Gemini", "source": "x_mock"},
        {"id": "x_010", "text": "中国発のAIツールが急成長中。DeepSeek、Qwen、Kuaishou Kling...グローバル市場での存在感が増している。",
         "author": "@global_ai_watch", "likes": 234, "retweets": 78, "created_at": now,
         "topic": "Chinese AI", "source": "x_mock"},
    ]
    return mock_posts


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "x_news_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"fetched_at": datetime.now().isoformat(), "count": len(posts),
                    "query": "AI news", "posts": posts}, f, ensure_ascii=False, indent=2)
    print(f"[X-NEWS] Raw data saved to {filepath}")
    return filepath


def run(query: str = "AI", limit: int = 20) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = search_x_news(query, limit)
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI news from X (Twitter)")
    parser.add_argument("--query", default="AI", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    args = parser.parse_args()
    results = run(args.query, args.limit)
    print(f"\n=== Results: {len(results)} posts found ===")
    for p in results:
        print(f"  [{p['likes']}♥] {p['text'][:60]}...")
