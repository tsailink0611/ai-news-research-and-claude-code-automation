"""
AI系RSSフィード取得スクリプト
厳選5ソースから最新記事を取得する（1ソース最大5件・合計25件上限）

ソース:
  - TechCrunch AI
  - VentureBeat AI
  - The Verge AI
  - Anthropic Blog
  - MIT Technology Review AI
"""
import json
import time
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, ensure_dirs_for_today

# 取得ソース定義（厳選5つ）
RSS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "limit": 5,
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "limit": 5,
    },
    {
        "name": "The Verge AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "limit": 5,
    },
    {
        "name": "Ars Technica Tech",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "limit": 4,
    },
    {
        "name": "MIT Tech Review AI",
        "url": "https://www.technologyreview.com/feed/",
        "limit": 4,
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)"
}


def fetch_article_body(url: str, timeout: int = 8) -> str:
    """記事URLから本文テキストを取得する（失敗時は空文字）"""
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 記事本文の候補タグを順番に試す
        for selector in ["article", "main", ".article-body", ".post-content", ".entry-content"]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                # 500字程度に絞る
                return text[:500]

        # fallback: bodyの最初の段落群
        paras = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paras[:5])
        return text[:500]
    except Exception:
        return ""


def parse_feed(source: dict) -> list[dict]:
    """1ソースのRSSを取得してパースする"""
    name = source["name"]
    url = source["url"]
    limit = source["limit"]

    print(f"  [{name}] 取得中...")

    try:
        # feedparserで取得
        feed = feedparser.parse(url)

        if not feed.entries:
            print(f"  [{name}] 記事なし（フィードが空）")
            return []

        articles = []
        for entry in feed.entries[:limit]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "")
            published = entry.get("published", "") or entry.get("updated", "")

            # サマリーをRSSのdescriptionから取得
            summary_raw = (
                entry.get("summary", "") or
                entry.get("description", "") or
                entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
            )

            # HTMLタグを除去
            if summary_raw:
                try:
                    from bs4 import BeautifulSoup
                    summary_text = BeautifulSoup(summary_raw, "html.parser").get_text(strip=True)[:400]
                except Exception:
                    summary_text = summary_raw[:400]
            else:
                summary_text = ""

            if not title or not link:
                continue

            article_id = hashlib.md5(link.encode()).hexdigest()[:12]

            articles.append({
                "id": article_id,
                "title": title,
                "url": link,
                "source": name,
                "source_type": "rss",
                "summary": summary_text,
                "published_at": published,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })

        print(f"  [{name}] {len(articles)} 件取得")
        return articles

    except Exception as e:
        print(f"  [{name}] エラー: {e}")
        return []


def run(fetch_body: bool = False) -> list[dict]:
    """
    全RSSソースから記事を取得する

    Args:
        fetch_body: Trueの場合、各記事URLから本文も取得する（遅くなる）

    Returns:
        記事リスト
    """
    date = ensure_dirs_for_today()
    out_path = RAW_DIR / date / "rss_articles.json"

    print(f"[fetch_rss] {len(RSS_SOURCES)} ソースから取得開始")
    all_articles = []

    for source in RSS_SOURCES:
        articles = parse_feed(source)

        # 本文取得オプション（重要記事のみ）
        if fetch_body and articles:
            for a in articles[:3]:  # 各ソースの上位3件のみ
                body = fetch_article_body(a["url"])
                if body and len(body) > 100:
                    a["body"] = body
                time.sleep(0.5)

        all_articles.extend(articles)
        time.sleep(0.3)  # ソース間の待機

    # 重複URL除去
    seen_urls = set()
    unique = []
    for a in all_articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            unique.append(a)

    print(f"\n[fetch_rss] 合計 {len(unique)} 件（重複除去後）")

    # 保存
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"[fetch_rss] 保存: {out_path}")

    return unique


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-body", action="store_true", help="記事本文も取得する")
    args = parser.parse_args()
    results = run(fetch_body=args.with_body)
    print(f"\n取得完了: {len(results)} 件")
    for a in results[:5]:
        print(f"  [{a['source']}] {a['title'][:60]}")
