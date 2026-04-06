"""
SerpApi Google検索分析スクリプト
SerpApi でAI関連キーワードのGoogle検索結果・サジェストを取得する。
APIキー未設定時はモックデータにフォールバック。
月250回の無料枠あり。

使い方:
    python scripts/fetch_serpapi.py
    python scripts/fetch_serpapi.py --query "Claude Code"
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, SERPAPI_KEY, ensure_dirs_for_today

SERPAPI_BASE = "https://serpapi.com/search"

DEFAULT_QUERIES = [
    "Claude Code",
    "AI agent framework 2026",
    "GPT-5 release",
    "best AI coding tools",
    "MCP protocol AI",
]


def search_google(query: str) -> dict:
    """SerpApi でGoogle検索結果を取得する"""
    if not SERPAPI_KEY:
        return _get_mock_search(query)

    try:
        return _search_via_api(query)
    except Exception as e:
        print(f"  [WARN] SerpApi error for '{query}': {e}")
        return _get_mock_search(query)


def _search_via_api(query: str) -> dict:
    """SerpApi 実API呼び出し"""
    params = {
        "q": query,
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "hl": "ja",
        "gl": "jp",
        "num": 10,
    }
    resp = requests.get(SERPAPI_BASE, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return {
        "query": query,
        "organic_results": [
            {
                "position": r.get("position", 0),
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in data.get("organic_results", [])[:10]
        ],
        "related_searches": [
            r.get("query", "") for r in data.get("related_searches", [])
        ],
    }


def get_autocomplete(query: str) -> list[str]:
    """SerpApi でGoogleオートコンプリート（サジェスト）を取得"""
    if not SERPAPI_KEY:
        return _get_mock_suggestions(query)

    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "engine": "google_autocomplete",
        }
        resp = requests.get(SERPAPI_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return [s.get("value", "") for s in data.get("suggestions", [])]
    except Exception as e:
        print(f"  [WARN] Autocomplete error: {e}")
        return _get_mock_suggestions(query)


def _get_mock_search(query: str) -> dict:
    """モック検索結果"""
    return {
        "query": query,
        "organic_results": [
            {"position": 1, "title": f"{query} - 最新情報まとめ", "link": "https://example.com/1",
             "snippet": f"{query}に関する最新の情報をまとめました。"},
            {"position": 2, "title": f"{query} の使い方・始め方ガイド", "link": "https://example.com/2",
             "snippet": f"{query}の基本的な使い方を解説します。"},
            {"position": 3, "title": f"{query} vs 競合比較 2026年版", "link": "https://example.com/3",
             "snippet": f"{query}と他のツールを徹底比較。"},
        ],
        "related_searches": [
            f"{query} 使い方", f"{query} API", f"{query} 料金",
            f"{query} 比較", f"{query} 最新",
        ],
    }


def _get_mock_suggestions(query: str) -> list[str]:
    """モックサジェスト"""
    return [
        f"{query} 使い方",
        f"{query} 料金",
        f"{query} API",
        f"{query} 比較",
        f"{query} チュートリアル",
    ]


def serp_to_items(all_results: list[dict], all_suggestions: dict) -> list[dict]:
    """検索結果をパイプライン統合用のアイテム形式に変換する"""
    items = []

    # サジェスト（急上昇キーワード）をアイテム化
    for query, suggestions in all_suggestions.items():
        for i, suggestion in enumerate(suggestions[:5]):
            items.append({
                "id": f"serp_suggest_{hash(suggestion) % 100000}",
                "title": f"Googleサジェスト: {suggestion}",
                "text": f"「{query}」のGoogle検索サジェストに「{suggestion}」が表示中。ユーザーの関心が高いキーワード。",
                "score": max(50 - i * 10, 10),
                "url": f"https://www.google.com/search?q={suggestion}",
                "topic": query,
                "source": "serpapi",
            })

    # 検索結果トップ記事をアイテム化
    for result in all_results:
        query = result.get("query", "")
        for organic in result.get("organic_results", [])[:3]:
            items.append({
                "id": f"serp_organic_{hash(organic.get('link', '')) % 100000}",
                "title": organic.get("title", ""),
                "text": organic.get("snippet", ""),
                "url": organic.get("link", ""),
                "score": max(30 - organic.get("position", 0) * 5, 5),
                "topic": query,
                "source": "serpapi",
            })

    return items


def fetch_all(queries: list[str] | None = None) -> tuple[list[dict], dict, list[dict]]:
    """全クエリの検索結果とサジェストを取得"""
    if queries is None:
        queries = DEFAULT_QUERIES

    has_key = bool(SERPAPI_KEY)
    if not has_key:
        print("[SERP] NOTE: Using mock data. Set SERPAPI_KEY in .env for real data.")

    all_results = []
    all_suggestions = {}

    for query in queries:
        print(f"[SERP] Searching: '{query}'")
        result = search_google(query)
        all_results.append(result)

        suggestions = get_autocomplete(query)
        all_suggestions[query] = suggestions
        print(f"  Results: {len(result.get('organic_results', []))}, Suggestions: {len(suggestions)}")

    items = serp_to_items(all_results, all_suggestions)
    print(f"[SERP] Generated {len(items)} items from {len(queries)} queries")
    return all_results, all_suggestions, items


def save_raw(results: list[dict], suggestions: dict, items: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "serpapi_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(items),
            "search_results": results,
            "suggestions": suggestions,
            "items": items,
        }, f, ensure_ascii=False, indent=2)
    print(f"[SERP] Raw data saved to {filepath}")
    return filepath


def run(query: str | None = None) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    if query:
        results, suggestions, items = fetch_all([query])
    else:
        results, suggestions, items = fetch_all()
    if items:
        save_raw(results, suggestions, items, date)
    return items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Google search analysis via SerpApi")
    parser.add_argument("--query", default=None, help="Search query")
    args = parser.parse_args()
    results = run(args.query)
    print(f"\n=== Results: {len(results)} items ===")
    for item in results[:10]:
        print(f"  [{item['score']}pts] {item['title'][:60]}...")
