"""
データ処理スクリプト
rawデータを読み込み、整形・スコアリング・重複排除して processed に保存する

使い方:
    python scripts/process_data.py
    python scripts/process_data.py --date 2026-04-06
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RAW_DIR, PROCESSED_DIR, AI_KEYWORDS, ensure_dirs_for_today, today_str,
    FRONTIER_SOURCES, PROPOSAL_SOURCES,
    FRONTIER_KEYWORDS, PROPOSAL_INDUSTRY_KEYWORDS,
    PROPOSAL_TOOL_KEYWORDS, PROPOSAL_SUBSIDY_KEYWORDS,
)


def load_raw_data(date: str) -> list[dict]:
    """指定日のrawデータをすべて読み込む"""
    raw_dir = RAW_DIR / date
    all_items = []

    if not raw_dir.exists():
        print(f"[PROCESS] No raw data found for {date}")
        return []

    for f in raw_dir.glob("*.json"):
        print(f"[PROCESS] Loading {f.name}")
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            # リスト形式（RSS等）
            if isinstance(data, list):
                all_items.extend(data)
            # HN形式
            elif "articles" in data:
                all_items.extend(data["articles"])
            # X形式
            elif "posts" in data:
                all_items.extend(data["posts"])
            # 汎用形式
            elif "items" in data:
                all_items.extend(data["items"])

    print(f"[PROCESS] Loaded {len(all_items)} total items")
    return all_items


def deduplicate(items: list[dict]) -> list[dict]:
    """タイトルまたはテキストベースで重複排除"""
    seen = set()
    unique = []
    for item in items:
        key = item.get("title") or item.get("text") or item.get("id", "")
        key = str(key).strip().lower()[:100]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def score_item(item: dict) -> float:
    """記事の重要度スコアを計算する"""
    score = 0.0

    # エンゲージメント
    score += min(item.get("score", 0) / 100, 5.0)
    score += min(item.get("likes", 0) / 100, 5.0)
    score += min(item.get("comments", 0) / 50, 3.0)
    score += min(item.get("retweets", 0) / 50, 3.0)

    # キーワードマッチ数
    text = f"{item.get('title', '')} {item.get('text', '')}".lower()
    kw_matches = sum(1 for kw in AI_KEYWORDS if kw in text)
    score += min(kw_matches * 0.5, 3.0)

    return round(score, 2)


def assign_lane(item: dict) -> str:
    """ソース名からFrontier/Proposalレーンを判定する"""
    source = item.get("source", "")
    source_type = item.get("source_type", "")
    if source in FRONTIER_SOURCES or source_type == "github_trending":
        return "frontier"
    if source in PROPOSAL_SOURCES or source_type == "japan_rss":
        return "proposal"
    # lang=ja の記事はデフォルトでproposal
    if item.get("lang") == "ja":
        return "proposal"
    return "frontier"


def calc_frontier_score(item: dict) -> float:
    """Frontier Score: 先端性・商材化候補としての価値"""
    score = 0.0
    text = (
        (item.get("title") or "") + " " +
        (item.get("summary") or "") + " " +
        (item.get("url") or "")
    ).lower()

    # キーワードマッチ
    kw_hits = sum(1 for kw in FRONTIER_KEYWORDS if kw in text)
    score += min(kw_hits * 0.6, 3.0)

    # GitHub Trending: スター数ボーナス
    stars = item.get("stars_today", 0)
    if stars:
        score += min(stars / 100, 2.0)
        score += 1.0  # GitHub自体がフロンティア

    # HackerNews: スコアボーナス
    if "hackernews" in (item.get("source") or "").lower():
        score += min(item.get("score", 0) / 200, 1.5)

    # Product Hunt
    if "product hunt" in (item.get("source") or "").lower():
        score += 1.0

    # 中国ソース（先行シグナル）
    if "china" in (item.get("source") or "").lower():
        score += 1.5

    # エンゲージメント補正
    score += min(item.get("importance_score", 0) * 0.3, 1.5)

    return round(min(score, 10.0), 1)


def calc_proposal_score(item: dict) -> float:
    """Proposal Score: 今すぐ提案に転用できる価値"""
    import re
    score = 0.0
    text = (
        (item.get("title") or "") + " " +
        (item.get("summary") or "") + " " +
        (item.get("summary_ja") or "")
    ).lower()

    # 業種キーワード（最重要）
    industry_hits = sum(1 for kw in PROPOSAL_INDUSTRY_KEYWORDS if kw in text)
    score += min(industry_hits * 1.5, 4.0)

    # ツール・サービスキーワード
    tool_hits = sum(1 for kw in PROPOSAL_TOOL_KEYWORDS if kw in text)
    score += min(tool_hits * 1.0, 3.0)

    # 補助金・助成金（最高優先度）
    subsidy_hits = sum(1 for kw in PROPOSAL_SUBSIDY_KEYWORDS if kw in text)
    score += min(subsidy_hits * 2.0, 4.0)

    # 数値・定量情報（提案根拠として機能する）
    if re.search(r'\d+\s*[%倍時間件万円分]', text):
        score += 1.0

    # 日本語・国内ソースボーナス
    if item.get("lang") == "ja" or item.get("source") in PROPOSAL_SOURCES:
        score += 1.0

    # いいね数（実際に読まれている国内記事）
    likes = item.get("likes", 0)
    if likes >= 10:
        score += min(likes / 20, 1.5)

    return round(min(score, 10.0), 1)


def enrich_items(items: list[dict]) -> list[dict]:
    """各アイテムにメタデータを追加する"""
    for item in items:
        item["importance_score"] = score_item(item)
        # レーン付与
        item["lane"] = assign_lane(item)
        # F軸・P軸スコア
        item["frontier_score"] = calc_frontier_score(item)
        item["proposal_score"] = calc_proposal_score(item)
        # 出力ブロック判定
        f = item["frontier_score"]
        p = item["proposal_score"]
        if p >= 5:
            item["output_block"] = "A"   # 今すぐ提案ネタ
        elif f >= 6 and p >= 2:
            item["output_block"] = "B"   # 今週触るべき先端シグナル
        elif f >= 4:
            item["output_block"] = "C"   # 将来ネタ保存
        else:
            item["output_block"] = "C"

        text = f"{item.get('title', '')} {item.get('text', '')}".lower()
        item["matched_keywords"] = [kw for kw in AI_KEYWORDS if kw in text]
        item["processed_at"] = datetime.now().isoformat()
    return items


def extract_topics(items: list[dict]) -> list[dict]:
    """主要トピックを抽出する"""
    topic_map = {}
    for item in items:
        topic = item.get("topic", "General AI")
        if topic not in topic_map:
            topic_map[topic] = {
                "topic": topic,
                "count": 0,
                "top_item": None,
                "max_score": 0,
            }
        topic_map[topic]["count"] += 1
        if item.get("importance_score", 0) > topic_map[topic]["max_score"]:
            topic_map[topic]["max_score"] = item["importance_score"]
            topic_map[topic]["top_item"] = item.get("title") or item.get("text", "")[:80]

    return sorted(topic_map.values(), key=lambda x: x["max_score"], reverse=True)


def process(date: str | None = None) -> dict:
    """メイン処理: raw → processed"""
    if date is None:
        date = ensure_dirs_for_today()
    else:
        (PROCESSED_DIR / date).mkdir(parents=True, exist_ok=True)

    items = load_raw_data(date)
    if not items:
        print("[PROCESS] No items to process")
        return {"items": [], "topics": [], "stats": {}}

    items = deduplicate(items)
    items = enrich_items(items)
    items.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
    topics = extract_topics(items)

    result = {
        "date": date,
        "processed_at": datetime.now().isoformat(),
        "stats": {
            "total_items": len(items),
            "sources": list(set(i.get("source", "unknown") for i in items)),
            "top_score": items[0]["importance_score"] if items else 0,
        },
        "topics": topics,
        "items": items,
    }

    # 保存
    filepath = PROCESSED_DIR / date / "processed_articles.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[PROCESS] Saved {len(items)} processed items to {filepath}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process raw AI news data")
    parser.add_argument("--date", default=None, help="Date to process (YYYY-MM-DD)")
    args = parser.parse_args()
    result = process(args.date)
    print(f"\n=== Processed: {result['stats'].get('total_items', 0)} items ===")
    for t in result.get("topics", [])[:5]:
        print(f"  [{t['max_score']:.1f}] {t['topic']} ({t['count']} items)")
