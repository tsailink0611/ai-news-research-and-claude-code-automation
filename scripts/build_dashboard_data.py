"""
ダッシュボード用データ生成スクリプト
各種データを集約してダッシュボードで表示できるJSON形式にする

使い方:
    python scripts/build_dashboard_data.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, LATEST_DIR, X_DRAFTS_DIR,
    DASHBOARD_DATA_DIR, RAW_DIR, ensure_dirs_for_today, today_str
)


def get_available_dates() -> list[str]:
    """データが存在する日付一覧を取得する"""
    dates = set()
    for d in [RAW_DIR, PROCESSED_DIR, DAILY_DIR]:
        if d.exists():
            for sub in d.iterdir():
                if sub.is_dir() and len(sub.name) == 10 and sub.name[4] == "-":
                    dates.add(sub.name)
    return sorted(dates, reverse=True)


def load_latest_processed() -> dict | None:
    """最新の処理済みデータを読み込む"""
    dates = get_available_dates()
    for date in dates:
        filepath = PROCESSED_DIR / date / "processed_articles.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def load_latest_drafts() -> dict | None:
    """最新のXドラフトを読み込む"""
    latest = LATEST_DIR / "latest_x_drafts.json"
    if latest.exists():
        with open(latest, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_latest_digest() -> str | None:
    """最新のダイジェストを読み込む"""
    latest = LATEST_DIR / "latest_digest.md"
    if latest.exists():
        with open(latest, "r", encoding="utf-8") as f:
            return f.read()
    return None


def build_dashboard_json() -> dict:
    """ダッシュボード用JSONを構築する"""
    dates = get_available_dates()
    processed = load_latest_processed()
    drafts_data = load_latest_drafts()
    digest_md = load_latest_digest()

    dashboard = {
        "generated_at": datetime.now().isoformat(),
        "available_dates": dates,
        "latest_date": dates[0] if dates else None,
        "stats": {
            "total_dates": len(dates),
            "total_articles": 0,
            "total_drafts": 0,
            "sources": [],
        },
        "topics": [],
        "top_articles": [],
        "x_drafts_preview": [],
        "digest_preview": "",
    }

    if processed:
        items = processed.get("items", [])
        dashboard["stats"]["total_articles"] = len(items)
        dashboard["stats"]["sources"] = processed.get("stats", {}).get("sources", [])
        dashboard["topics"] = processed.get("topics", [])[:10]

        # スコア順ソート済みの全記事
        sorted_items = sorted(
            items,
            key=lambda x: float(x.get("importance_score") or x.get("score") or 0),
            reverse=True
        )

        # 上位15件（トップ記事）
        dashboard["top_articles"] = [
            {
                "title": item.get("title") or item.get("text", "")[:80],
                "score": float(item.get("importance_score") or item.get("score") or 0),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "topic": item.get("topic", ""),
                "summary_ja": item.get("summary_ja", ""),
                "point": item.get("point", ""),
            }
            for item in sorted_items[:15]
        ]

        # カテゴリー別全記事
        from collections import defaultdict
        by_cat = defaultdict(list)
        for item in sorted_items:
            cat = item.get("topic") or "その他"
            by_cat[cat].append({
                "title": item.get("title") or item.get("text", "")[:80],
                "score": float(item.get("importance_score") or item.get("score") or 0),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
                "summary_ja": item.get("summary_ja", ""),
                "point": item.get("point", ""),
            })
        # カテゴリーを記事数順にソート
        dashboard["articles_by_category"] = {
            cat: articles
            for cat, articles in sorted(by_cat.items(), key=lambda x: -len(x[1]))
        }

    if drafts_data:
        drafts = drafts_data.get("drafts", [])
        dashboard["stats"]["total_drafts"] = len(drafts)
        dashboard["x_drafts_preview"] = [
            {
                "text": d.get("draft_text", ""),
                "style": d.get("style_label", ""),
                "style_key": d.get("style", ""),
                "topic": d.get("topic", ""),
                "urgency": d.get("urgency", ""),
                "char_count": d.get("char_count", 0),
                "recommended_use": d.get("recommended_use", ""),
            }
            for d in drafts
        ]

    if digest_md:
        dashboard["digest_preview"] = digest_md[:1000]

    return dashboard


def save_dashboard_data(dashboard: dict) -> Path:
    """ダッシュボードデータを保存する"""
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DASHBOARD_DATA_DIR / "dashboard.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    print(f"[DASHBOARD] Data saved to {filepath}")
    return filepath


def run() -> dict:
    """メイン実行"""
    ensure_dirs_for_today()
    dashboard = build_dashboard_json()
    save_dashboard_data(dashboard)
    return dashboard


if __name__ == "__main__":
    result = run()
    stats = result.get("stats", {})
    print(f"\n=== Dashboard Data Generated ===")
    print(f"  Dates: {stats.get('total_dates', 0)}")
    print(f"  Articles: {stats.get('total_articles', 0)}")
    print(f"  Drafts: {stats.get('total_drafts', 0)}")
    print(f"  Sources: {', '.join(stats.get('sources', []))}")
