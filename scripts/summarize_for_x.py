"""
X向け再要約スクリプト
スコア上位10記事を1記事1ドラフトで生成する。
Claude API を使って自然な日本語投稿文を作成する。
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, LATEST_DIR, X_CHAR_LIMIT,
    DRAFT_STYLES, ANTHROPIC_API_KEY, CLAUDE_MODEL,
    ensure_dirs_for_today, today_str
)

# X向けに絞る記事数
TOP_N_FOR_X = 10


def _get_claude_client():
    if not ANTHROPIC_API_KEY:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_processed(date: str) -> dict | None:
    filepath = PROCESSED_DIR / date / "processed_articles.json"
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _pick_style(item: dict) -> str:
    """記事内容からベストなスタイルを1つ選ぶ"""
    title = (item.get("title") or "").lower()
    summary = (item.get("summary_ja") or item.get("summary") or "").lower()
    score = item.get("importance_score", 0)
    text = title + " " + summary

    if score >= 5.0:
        return "breaking"
    if any(w in text for w in ["vs", "比較", "versus", "compare", "difference"]):
        return "comparison"
    if any(w in text for w in ["how", "why", "什么", "仕組み", "解説", "とは"]):
        return "explainer"
    if any(w in text for w in ["業務", "実務", "仕事", "使い方", "活用", "workflow"]):
        return "practical"
    if score >= 3.0:
        return "opinion"
    return "breaking"


def _get_recommended_use(style: str, score: float) -> str:
    if score >= 5.0:
        return "即時投稿推奨"
    if style == "explainer":
        return "教育・価値提供向け"
    if style == "practical":
        return "エンゲージメント重視"
    if style == "beginner":
        return "新規フォロワー獲得向け"
    return "通常スケジュール投稿"


def create_draft_with_claude(client, item: dict, style: str) -> str:
    """Claude API で自然な日本語X投稿文を生成する"""
    title = item.get("title") or ""
    summary_ja = item.get("summary_ja") or item.get("summary") or ""
    point = item.get("point") or ""
    topic = item.get("topic", "AI")
    url = item.get("url", "")
    style_info = DRAFT_STYLES.get(style, {})
    style_label = style_info.get("label", style)

    context = point if point else (summary_ja[:150] if summary_ja else title)

    prompt = f"""X（旧Twitter）に投稿する日本語テキストを1つ書いてください。

## 元記事の情報
タイトル: {title}
要点: {context}
トピック: {topic}
スタイル: {style_label}

## 書き方のルール（必ず守ること）
- 140〜200文字で書く（URLは後で付けるので含めない）
- ハッシュタグは末尾に2〜3個だけ（#AI は必須）
- 「です・ます」調で書く。ただし全文同じ語尾を繰り返さない
- 「画期的」「革新的」「注目」「必見」「衝撃」は使わない
- 「〜してみた」「〜ですね」「〜ですよね」は使わない
- 記事の具体的な内容や数値・事実を1つ以上入れる
- 絵文字は使わない
- 読んだ人が「なるほど」と思える実質的な情報を入れる
- 「AIがすごい」「重要です」のような空虚な表現を避ける
- テンプレートっぽい書き出しを避ける（【速報】などのブラケットも不要）

投稿テキストだけを出力してください。説明文は不要です。"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=350,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _fallback_draft(item: dict, style: str) -> str:
    """Claude APIなし時のフォールバック"""
    point = item.get("point") or ""
    title = item.get("title") or ""
    topic = item.get("topic", "AI")
    tag = topic.replace(" ", "")

    if point:
        return f"{point}\n\n詳細は元記事を確認してください。\n#AI #{tag}"
    return f"{title[:100]}\n\n{topic}分野の最新動向として注目されています。\n#AI #{tag}"


def summarize_all(date: str) -> list[dict]:
    """上位10記事をスコア順に処理し、1記事1ドラフトを生成する"""
    data = load_processed(date)
    if not data:
        print(f"[X-SUMMARY] No processed data for {date}")
        return []

    items = data.get("items", [])
    # importance_scoreでソート済みのはずだが念のため
    items = sorted(items, key=lambda x: x.get("importance_score", 0), reverse=True)
    items = items[:TOP_N_FOR_X]

    client = _get_claude_client()
    if client:
        print(f"[X-SUMMARY] Claude API使用 ({CLAUDE_MODEL}) - {len(items)} 件")
    else:
        print("[X-SUMMARY] APIキーなし → テンプレート生成")

    summaries = []
    for i, item in enumerate(items):
        style = _pick_style(item)
        title_short = (item.get("title") or "")[:40]
        try:
            if client:
                text = create_draft_with_claude(client, item, style)
            else:
                text = _fallback_draft(item, style)
            text = text[:X_CHAR_LIMIT]
        except Exception as e:
            print(f"[X-SUMMARY] エラー ({title_short}): {e}")
            text = _fallback_draft(item, style)

        score = item.get("importance_score", 0)
        summaries.append({
            "topic": item.get("topic", "AI"),
            "source_type": item.get("source", "unknown"),
            "style": style,
            "style_label": DRAFT_STYLES.get(style, {}).get("label", style),
            "urgency": "high" if score >= 5.0 else "medium" if score >= 3.0 else "low",
            "recommended_use": _get_recommended_use(style, score),
            "draft_text": text,
            "char_count": len(text),
            "original_title": item.get("title") or "",
            "importance_score": score,
            "generated_by": "claude" if client else "template",
        })
        print(f"  [{i+1}/{len(items)}] {style} | {title_short}")

    print(f"[X-SUMMARY] {len(summaries)} 件生成完了")
    return summaries


def save_summaries(summaries: list[dict], date: str) -> Path:
    filepath = DAILY_DIR / date / "x_summaries.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "count": len(summaries),
            "summaries": summaries,
        }, f, ensure_ascii=False, indent=2)
    print(f"[X-SUMMARY] 保存: {filepath}")
    return filepath


def run(date: str | None = None) -> list[dict]:
    if date is None:
        date = ensure_dirs_for_today()
    summaries = summarize_all(date)
    if summaries:
        save_summaries(summaries, date)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    results = run(args.date)
    print(f"\n=== {len(results)} summaries ===")
    for s in results[:5]:
        print(f"  [{s['style_label']}] {s['draft_text'][:80]}...")
