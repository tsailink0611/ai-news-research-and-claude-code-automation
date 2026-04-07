"""
Google Trends AIキーワード分析スクリプト
pytrends ライブラリを使ってAIキーワードの検索トレンドを取得する。
APIキー不要。

使い方:
    python scripts/fetch_google_trends.py
    python scripts/fetch_google_trends.py --keywords "Claude Code" "GPT-5" "AI agents"
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, ensure_dirs_for_today

DEFAULT_KEYWORDS = [
    ["Claude Code", "Cursor AI", "Windsurf AI", "GitHub Copilot", "Devin AI"],
    ["OpenAI", "Anthropic", "Google Gemini", "DeepSeek", "Mistral AI"],
    ["AI agent", "RAG", "LLM", "MCP protocol", "AI coding"],
]


def fetch_trends(keywords: list[str], timeframe: str = "now 7-d") -> dict:
    """Google Trends からキーワードのトレンドを取得する"""
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ja-JP", tz=540)
        pytrends.build_payload(keywords[:5], timeframe=timeframe, geo="")

        # トレンドデータ取得
        interest = pytrends.interest_over_time()
        related = {}
        for kw in keywords[:5]:
            try:
                rq = pytrends.related_queries()
                if kw in rq:
                    top = rq[kw].get("top")
                    rising = rq[kw].get("rising")
                    related[kw] = {
                        "top": top.to_dict("records") if top is not None and not top.empty else [],
                        "rising": rising.to_dict("records") if rising is not None and not rising.empty else [],
                    }
            except Exception:
                pass

        result = {
            "keywords": keywords,
            "timeframe": timeframe,
            "interest_over_time": interest.to_dict("records") if not interest.empty else [],
            "related_queries": related,
        }

        print(f"[TRENDS] Fetched trends for: {', '.join(keywords)}")
        return result

    except ImportError:
        print("[TRENDS] pytrends not installed. Using mock data.")
        return _get_mock_trends(keywords)
    except Exception as e:
        print(f"[TRENDS] Error: {e}. Using mock data.")
        return _get_mock_trends(keywords)


def _get_mock_trends(keywords: list[str]) -> dict:
    """モックトレンドデータ"""
    return {
        "keywords": keywords,
        "timeframe": "now 7-d",
        "interest_over_time": [],
        "related_queries": {
            kw: {
                "top": [{"query": f"{kw} 使い方", "value": 100}, {"query": f"{kw} 比較", "value": 75}],
                "rising": [{"query": f"{kw} 最新", "value": 500}, {"query": f"{kw} API", "value": 300}],
            }
            for kw in keywords[:5]
        },
    }


def trends_to_items(trends_data: list[dict]) -> list[dict]:
    """トレンドデータを記事形式に変換する（パイプライン統合用）"""
    items = []
    for trend in trends_data:
        for kw in trend.get("keywords", []):
            related = trend.get("related_queries", {}).get(kw, {})
            rising = related.get("rising", [])

            # 急上昇クエリをニュースアイテムとして変換
            for rq in rising[:3]:
                query = rq.get("query", "")
                value = rq.get("value", 0)
                items.append({
                    "id": f"gtrend_{hash(query) % 100000}",
                    "title": f"Google検索急上昇: {query}",
                    "text": f"「{query}」がGoogle検索で急上昇中（+{value}%）。キーワード「{kw}」の関連。",
                    "score": min(value // 10, 100),
                    "url": f"https://trends.google.com/trends/explore?q={query}",
                    "topic": kw,
                    "source": "google_trends",
                })
    return items


def fetch_all(keyword_groups: list[list[str]] | None = None) -> tuple[list[dict], list[dict]]:
    """全キーワードグループのトレンドを取得"""
    if keyword_groups is None:
        keyword_groups = DEFAULT_KEYWORDS

    all_trends = []
    for group in keyword_groups:
        print(f"[TRENDS] Querying: {', '.join(group)}")
        trends = fetch_trends(group)
        all_trends.append(trends)

    items = trends_to_items(all_trends)
    print(f"[TRENDS] Generated {len(items)} trend items")
    return all_trends, items


def save_raw(trends: list[dict], items: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "google_trends_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(items),
            "trends_data": trends,
            "items": items,
        }, f, ensure_ascii=False, indent=2)
    print(f"[TRENDS] Raw data saved to {filepath}")
    return filepath


def run(keywords: list[str] | None = None) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    if keywords:
        trends, items = fetch_all([keywords])
    else:
        trends, items = fetch_all()
    if items:
        save_raw(trends, items, date)
    return items


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI keyword trends from Google Trends")
    parser.add_argument("--keywords", nargs="+", default=None, help="Keywords to track")
    args = parser.parse_args()
    results = run(args.keywords)
    print(f"\n=== Results: {len(results)} trend items ===")
    for item in results[:10]:
        print(f"  [{item['score']}pts] {item['title'][:60]}...")
