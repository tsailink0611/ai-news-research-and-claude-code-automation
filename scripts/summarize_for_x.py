"""
X向け再要約スクリプト
保存済みデータを元に、X投稿に適した短文要約を生成する

使い方:
    python scripts/summarize_for_x.py
    python scripts/summarize_for_x.py --date 2026-04-06
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, LATEST_DIR, X_CHAR_LIMIT,
    DRAFT_STYLES, ensure_dirs_for_today, today_str
)


def load_processed(date: str) -> dict | None:
    filepath = PROCESSED_DIR / date / "processed_articles.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def create_summary_for_item(item: dict, style: str) -> dict:
    """1アイテムに対して指定スタイルの要約を作成する"""
    title = item.get("title") or item.get("text", "")[:80]
    topic = item.get("topic", "AI")
    source = item.get("source", "unknown")
    score = item.get("importance_score", 0)

    templates = {
        "breaking": _template_breaking,
        "explainer": _template_explainer,
        "comparison": _template_comparison,
        "opinion": _template_opinion,
        "beginner": _template_beginner,
        "practical": _template_practical,
    }

    generator = templates.get(style, _template_breaking)
    text = generator(title, topic)

    return {
        "topic": topic,
        "source_type": source,
        "style": style,
        "style_label": DRAFT_STYLES.get(style, {}).get("label", style),
        "urgency": "high" if score >= 5.0 else "medium" if score >= 3.0 else "low",
        "recommended_use": _get_recommended_use(style, score),
        "draft_text": text[:X_CHAR_LIMIT],
        "char_count": len(text[:X_CHAR_LIMIT]),
        "original_title": title,
    }


def _template_breaking(title: str, topic: str) -> str:
    return f"🚀【速報】{title}\n\n{topic}の最新動向。AI業界に大きなインパクトを与えそうな展開です。\n\n詳細は続報で。\n#AI #{topic.replace(' ', '')}"


def _template_explainer(title: str, topic: str) -> str:
    return f"📝【解説】{title}\n\nなぜこれが重要なのか？\n→ {topic}分野での技術的ブレークスルーの可能性\n→ 開発者・ビジネス両面への影響\n\n要点を整理します👇\n#AI #{topic.replace(' ', '')}"


def _template_comparison(title: str, topic: str) -> str:
    return f"⚖️【比較】{title}\n\n他のアプローチとの違いは？\n✅ 強み: 新しい技術的アプローチ\n⚠️ 課題: まだ発展途上の部分も\n\n選ぶ基準を解説。\n#AI #{topic.replace(' ', '')}"


def _template_opinion(title: str, topic: str) -> str:
    return f"💭【考察】{title}\n\n個人的な見解ですが、{topic}の方向性として非常に示唆的。\n\nこの流れが加速すると、AI開発の常識が変わるかもしれません。\n#AI #{topic.replace(' ', '')}"


def _template_beginner(title: str, topic: str) -> str:
    return f"📚【初心者向け】{title}\n\nわかりやすく言うと...\n{topic}とは、AIをより便利に使うための技術のこと。\n\n今知っておくべきポイントをまとめました。\n#AI入門 #{topic.replace(' ', '')}"


def _template_practical(title: str, topic: str) -> str:
    return f"💼【実務活用】{title}\n\nこれ、実際の仕事でどう使える？\n→ 作業効率化のヒント\n→ 導入時の注意点\n\n明日から試せるアクションプランを紹介。\n#AI活用 #{topic.replace(' ', '')}"


def _get_recommended_use(style: str, score: float) -> str:
    if score >= 5.0:
        return "即時投稿推奨 - 速報性が高い"
    if style == "explainer":
        return "フォロワー教育・価値提供に最適"
    if style == "practical":
        return "エンゲージメント重視の投稿に"
    if style == "beginner":
        return "新規フォロワー獲得向け"
    return "通常投稿スケジュールで"


def summarize_all(date: str, styles: list[str] | None = None) -> list[dict]:
    """全アイテムを複数スタイルで要約する"""
    data = load_processed(date)
    if not data:
        print(f"[X-SUMMARY] No processed data for {date}")
        return []

    items = data.get("items", [])[:15]  # 上位15件に絞る
    if styles is None:
        styles = list(DRAFT_STYLES.keys())

    summaries = []
    for item in items:
        for style in styles:
            summary = create_summary_for_item(item, style)
            summaries.append(summary)

    print(f"[X-SUMMARY] Generated {len(summaries)} summaries from {len(items)} items")
    return summaries


def save_summaries(summaries: list[dict], date: str) -> Path:
    """要約をJSONで保存する"""
    filepath = DAILY_DIR / date / "x_summaries.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "count": len(summaries),
            "summaries": summaries,
        }, f, ensure_ascii=False, indent=2)
    print(f"[X-SUMMARY] Saved to {filepath}")
    return filepath


def run(date: str | None = None) -> list[dict]:
    """メイン実行"""
    if date is None:
        date = ensure_dirs_for_today()

    summaries = summarize_all(date)
    if summaries:
        save_summaries(summaries, date)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize for X posts")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD)")
    args = parser.parse_args()
    results = run(args.date)
    print(f"\n=== {len(results)} summaries generated ===")
    for s in results[:5]:
        print(f"  [{s['style_label']}] {s['draft_text'][:60]}...")
