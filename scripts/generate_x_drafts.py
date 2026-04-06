"""
Xドラフト量産スクリプト
保存済みデータから20〜30本のX投稿ドラフトを生成する

使い方:
    python scripts/generate_x_drafts.py
    python scripts/generate_x_drafts.py --date 2026-04-06 --count 30
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, LATEST_DIR, X_DRAFTS_DIR,
    MAX_X_DRAFTS, X_CHAR_LIMIT, DRAFT_STYLES,
    ensure_dirs_for_today, today_str
)


def load_summaries(date: str) -> list[dict]:
    """X向け要約を読み込む"""
    filepath = DAILY_DIR / date / "x_summaries.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("summaries", [])

    # 要約がない場合は処理済みデータから直接生成
    filepath = PROCESSED_DIR / date / "processed_articles.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return _quick_drafts_from_processed(data)
    return []


def _quick_drafts_from_processed(data: dict) -> list[dict]:
    """処理済みデータから簡易ドラフトを生成する"""
    items = data.get("items", [])[:10]
    drafts = []
    for item in items:
        title = item.get("title") or item.get("text", "")[:80]
        topic = item.get("topic", "AI")
        for style_key, style_info in DRAFT_STYLES.items():
            drafts.append({
                "topic": topic,
                "source_type": item.get("source", "unknown"),
                "style": style_key,
                "style_label": style_info["label"],
                "urgency": "medium",
                "recommended_use": "通常投稿",
                "draft_text": f"【{style_info['label']}】{title}",
                "original_title": title,
            })
    return drafts


def select_best_drafts(summaries: list[dict], count: int = 30) -> list[dict]:
    """最適なドラフトを選定する"""
    # 優先度: high urgency → diverse styles → diverse topics
    high = [s for s in summaries if s.get("urgency") == "high"]
    medium = [s for s in summaries if s.get("urgency") == "medium"]
    low = [s for s in summaries if s.get("urgency") == "low"]

    selected = []
    seen_combos = set()

    for pool in [high, medium, low]:
        for item in pool:
            combo = (item.get("topic", ""), item.get("style", ""))
            if combo not in seen_combos:
                seen_combos.add(combo)
                selected.append(item)
            if len(selected) >= count:
                break
        if len(selected) >= count:
            break

    # まだ足りない場合は残りを追加
    if len(selected) < count:
        for item in summaries:
            if item not in selected:
                selected.append(item)
            if len(selected) >= count:
                break

    return selected[:count]


def format_drafts_markdown(drafts: list[dict], date: str) -> str:
    """ドラフト一覧をMarkdownで整形する"""
    lines = []
    lines.append(f"# X投稿ドラフト - {date}")
    lines.append(f"\n> 生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> ドラフト数: {len(drafts)}本")
    lines.append(f"> スタイル: {', '.join(set(d.get('style_label', '') for d in drafts))}")

    lines.append("\n---\n")

    # スタイル別の統計
    style_counts = {}
    for d in drafts:
        sl = d.get("style_label", "不明")
        style_counts[sl] = style_counts.get(sl, 0) + 1
    lines.append("## 📊 スタイル別内訳\n")
    for sl, cnt in sorted(style_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {sl}: {cnt}本")

    lines.append("\n---\n")

    # ドラフト本文
    for i, draft in enumerate(drafts, 1):
        urgency_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(draft.get("urgency", "low"), "⚪")

        lines.append(f"## Draft #{i:02d}")
        lines.append(f"- **トピック**: {draft.get('topic', 'N/A')}")
        lines.append(f"- **スタイル**: {draft.get('style_label', 'N/A')}")
        lines.append(f"- **緊急度**: {urgency_icon} {draft.get('urgency', 'N/A')}")
        lines.append(f"- **推奨用途**: {draft.get('recommended_use', 'N/A')}")
        lines.append(f"- **ソース**: {draft.get('source_type', 'N/A')}")
        lines.append(f"- **文字数**: {len(draft.get('draft_text', ''))}文字")
        lines.append("")
        lines.append("```")
        lines.append(draft.get("draft_text", ""))
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def save_drafts(drafts: list[dict], markdown: str, date: str) -> dict:
    """ドラフトをJSON + Markdownで保存する"""
    paths = {}

    # JSON保存
    json_path = X_DRAFTS_DIR / date / "x_drafts.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "count": len(drafts),
            "drafts": drafts,
        }, f, ensure_ascii=False, indent=2)
    paths["json"] = json_path

    # Markdown保存（日次）
    md_path = X_DRAFTS_DIR / date / "x_drafts.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    paths["markdown"] = md_path

    # latest更新
    latest_md = LATEST_DIR / "latest_x_drafts.md"
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(markdown)
    paths["latest_md"] = latest_md

    latest_json = LATEST_DIR / "latest_x_drafts.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump({
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "count": len(drafts),
            "drafts": drafts,
        }, f, ensure_ascii=False, indent=2)
    paths["latest_json"] = latest_json

    for label, p in paths.items():
        print(f"[X-DRAFTS] Saved {label}: {p}")

    return paths


def run(date: str | None = None, count: int | None = None) -> list[dict]:
    """メイン実行"""
    if date is None:
        date = ensure_dirs_for_today()
    if count is None:
        count = MAX_X_DRAFTS

    summaries = load_summaries(date)
    if not summaries:
        print(f"[X-DRAFTS] No summaries found for {date}")
        return []

    drafts = select_best_drafts(summaries, count)
    markdown = format_drafts_markdown(drafts, date)
    save_drafts(drafts, markdown, date)

    print(f"\n[X-DRAFTS] Generated {len(drafts)} drafts for {date}")
    return drafts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate X post drafts")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument("--count", type=int, default=None, help="Number of drafts")
    args = parser.parse_args()
    results = run(args.date, args.count)
    print(f"\n=== {len(results)} drafts generated ===")
