"""
日本国内AIニュース取得スクリプト（エンゲージメント重視）
いいね数・ビュー数・閲覧数でフィルタリングし、実際に読まれている記事のみ取得する

ソース別の品質基準:
  - Zenn: liked_count >= 10（APIでいいね順取得）
  - Qiita: likes_count >= 5（APIでスコア順取得）
  - ITmedia AI+: 編集部が選んだ記事（エンゲージメントデータなし・信頼性で選別）
  - AINOW: 編集部キュレーション（同上）
"""
import json
import hashlib
import requests
import feedparser
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, ensure_dirs_for_today

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)"}

# エンゲージメント閾値
ZENN_MIN_LIKES = 10      # Zenn: いいね10以上
QIITA_MIN_LIKES = 5      # Qiita: いいね5以上
GITHUB_TREND_MIN_STARS = 5  # GitHub: 今日スター5以上

# 日本語AI関連キーワード（スコアリング用）
JP_AI_KEYWORDS = [
    "ai", "人工知能", "機械学習", "深層学習", "生成ai", "chatgpt", "claude", "gemini",
    "llm", "大規模言語モデル", "自動化", "dx", "デジタルトランスフォーメーション",
    "業務効率化", "活用事例", "導入", "中小企業", "製造業", "不動産", "建設",
    "n8n", "ノーコード", "ローコード", "rpa", "ワークフロー",
    "エージェント", "rag", "ベクトル", "ファインチューニング", "プロンプト",
    "openai", "anthropic", "google", "microsoft",
]


def _score_item(title: str, summary: str, likes: int = 0) -> float:
    text = (title + " " + summary).lower()
    kw_matches = sum(1 for kw in JP_AI_KEYWORDS if kw.lower() in text)
    base = round(min(kw_matches * 0.4, 3.0), 2)
    engagement_bonus = round(min(likes / 20, 2.0), 2)
    return round(base + engagement_bonus, 2)


# ─── Zenn API（いいね順） ───────────────────────────────────────────

def fetch_zenn_api(limit: int = 8) -> list[dict]:
    """Zenn APIからいいね数でフィルタした記事を取得する"""
    print("  [Zenn] API取得中（いいね順）...")
    url = "https://zenn.dev/api/articles?topics=ai&order=liked&count=20"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        articles_raw = data.get("articles", [])

        results = []
        for a in articles_raw:
            liked = a.get("liked_count", 0)
            if liked < ZENN_MIN_LIKES:
                continue  # いいね数不足はスキップ

            title = a.get("title", "").strip()
            slug = a.get("slug", "")
            user = a.get("user", {}).get("username", "")
            link = f"https://zenn.dev/{user}/articles/{slug}" if user and slug else ""
            if not title or not link:
                continue

            article_id = hashlib.md5(link.encode()).hexdigest()[:12]
            score = _score_item(title, "", liked)

            results.append({
                "id": article_id,
                "title": title,
                "url": link,
                "source": "Zenn AI",
                "source_type": "japan_rss",
                "topic": "Japan Dev AI",
                "summary": f"いいね {liked} | Zenn技術記事",
                "likes": liked,
                "published_at": a.get("published_at", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "score": score,
                "importance_score": score,
                "lang": "ja",
            })
            if len(results) >= limit:
                break

        results.sort(key=lambda x: x.get("likes", 0), reverse=True)
        print(f"  [Zenn] {len(results)} 件取得（いいね{ZENN_MIN_LIKES}以上）")
        return results

    except Exception as e:
        print(f"  [Zenn] エラー: {e}")
        return []


# ─── Qiita API（いいね数でフィルタ） ──────────────────────────────

def fetch_qiita_api(limit: int = 6) -> list[dict]:
    """Qiita APIからいいね付き記事を取得する（複数ページを走査して絞り込み）"""
    print("  [Qiita] API取得中（いいね順フィルタ）...")
    collected = []

    for page in range(1, 4):  # 最大3ページ走査
        url = f"https://qiita.com/api/v2/tags/ai/items?per_page=20&page={page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            items = resp.json()
            if not items:
                break

            for it in items:
                liked = it.get("likes_count", 0)
                if liked < QIITA_MIN_LIKES:
                    continue

                title = it.get("title", "").strip()
                link = it.get("url", "")
                if not title or not link:
                    continue

                tags = [t.get("name", "") for t in it.get("tags", [])]
                summary = f"いいね {liked} | タグ: {', '.join(tags[:4])}"
                article_id = hashlib.md5(link.encode()).hexdigest()[:12]
                score = _score_item(title, " ".join(tags), liked)

                collected.append({
                    "id": article_id,
                    "title": title,
                    "url": link,
                    "source": "Qiita AI",
                    "source_type": "japan_rss",
                    "topic": "Japan Dev AI",
                    "summary": summary,
                    "likes": liked,
                    "published_at": it.get("created_at", ""),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "score": score,
                    "importance_score": score,
                    "lang": "ja",
                })

            time.sleep(0.5)
        except Exception as e:
            print(f"  [Qiita] p{page} エラー: {e}")
            break

    collected.sort(key=lambda x: x.get("likes", 0), reverse=True)
    results = collected[:limit]
    print(f"  [Qiita] {len(results)} 件取得（いいね{QIITA_MIN_LIKES}以上）")
    return results


# ─── RSS系（編集部キュレーション） ────────────────────────────────

EDITORIAL_RSS = [
    {
        "name": "ITmedia AI+",
        "url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
        "limit": 6,
        "topic": "Japan AI Industry",
    },
    {
        "name": "AINOW",
        "url": "https://ainow.ai/feed/",
        "limit": 4,
        "topic": "Japan AI Business",
    },
    {
        # 日経クロステック：大企業DX・製造業AI活用の国内最大メディア
        # 全記事フィードなのでAIキーワードでフィルタリング
        "name": "日経クロステック",
        "url": "https://xtech.nikkei.com/rss/index.rdf",
        "limit": 5,
        "topic": "Japan AI Industry",
        "filter_keywords": [
            "ai", "人工知能", "生成ai", "llm", "chatgpt", "claude", "gemini",
            "dx", "デジタル変革", "自動化", "業務効率", "導入", "活用",
            "データ分析", "機械学習", "ロボット", "rpa",
        ],
    },
]


def fetch_editorial_rss() -> list[dict]:
    """編集部キュレーションRSSを取得する（ITmedia / AINOW）"""
    all_articles = []
    for src in EDITORIAL_RSS:
        name = src["name"]
        filter_kw = src.get("filter_keywords")
        print(f"  [{name}] RSS取得中...")
        try:
            feed = feedparser.parse(src["url"])
            count = 0
            # フィルターあり（日経等）は多めに走査してlimitまで絞る
            scan_limit = src["limit"] * 10 if filter_kw else src["limit"]
            for entry in feed.entries[:scan_limit]:
                if count >= src["limit"]:
                    break
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if not title or not link:
                    continue

                # キーワードフィルター適用
                if filter_kw:
                    text = (title + " " + entry.get("summary", "")).lower()
                    if not any(kw.lower() in text for kw in filter_kw):
                        continue

                summary_raw = entry.get("summary", "") or entry.get("description", "")
                if summary_raw:
                    try:
                        from bs4 import BeautifulSoup
                        summary_text = BeautifulSoup(summary_raw, "html.parser").get_text(strip=True)[:250]
                    except Exception:
                        summary_text = summary_raw[:250]
                else:
                    summary_text = "編集部キュレーション記事"

                article_id = hashlib.md5(link.encode()).hexdigest()[:12]
                score = _score_item(title, summary_text)

                all_articles.append({
                    "id": article_id,
                    "title": title,
                    "url": link,
                    "source": name,
                    "source_type": "japan_rss",
                    "topic": src["topic"],
                    "summary": summary_text,
                    "likes": 0,
                    "published_at": entry.get("published", ""),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "score": score,
                    "importance_score": score,
                    "lang": "ja",
                })
                count += 1
            print(f"  [{name}] {count} 件取得")
        except Exception as e:
            print(f"  [{name}] エラー: {e}")

    return all_articles


# ─── メイン処理 ────────────────────────────────────────────────

def run() -> list[dict]:
    """
    日本語AIニュースをエンゲージメント基準で取得する

    Returns:
        記事リスト（いいね/スター付き記事を優先）
    """
    date = ensure_dirs_for_today()
    out_path = RAW_DIR / date / "japan_ai_news.json"

    print("[fetch_japan] 日本語AIニュース取得開始（エンゲージメント重視）")

    all_articles = []

    # APIソース（エンゲージメント付き）
    all_articles.extend(fetch_zenn_api(limit=8))
    all_articles.extend(fetch_qiita_api(limit=6))

    # 編集部キュレーション（業界ニュース）
    all_articles.extend(fetch_editorial_rss())

    # URL重複排除
    seen_urls = set()
    unique = []
    for a in all_articles:
        if a["url"] not in seen_urls:
            seen_urls.add(a["url"])
            unique.append(a)

    # いいね数 → importance_score の順でソート
    unique.sort(key=lambda x: (x.get("likes", 0), x.get("importance_score", 0)), reverse=True)

    print(f"\n[fetch_japan] 合計 {len(unique)} 件（重複除去後）")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"[fetch_japan] 保存: {out_path}")

    return unique


if __name__ == "__main__":
    import io
    import sys as _sys
    _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8")
    results = run()
    print(f"\n=== 取得完了: {len(results)} 件 ===")
    for a in results[:10]:
        likes = a.get("likes", 0)
        mark = f"いいね{likes}" if likes > 0 else "編集部"
        print(f"  [{mark:>7}] [{a['source']}] {a['title'][:55]}")
