"""
記事の日本語要約生成スクリプト
processed_articles.json の各記事にClaudeで日本語要約を追加する
"""
import os
import json
import time
import argparse
from pathlib import Path

try:
    import anthropic
except ImportError:
    anthropic = None

from config import PROCESSED_DIR, today_str, ANTHROPIC_API_KEY, CLAUDE_MODEL

HAIKU_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 5  # 1回のAPIコールで処理する記事数
TOP_N = 40      # 要約対象の上位N件（スコア順）


def build_batch_prompt(articles: list) -> str:
    """バッチ処理用プロンプトを生成する"""
    lines = ["以下の記事それぞれについて、日本語で要約してください。\n"]
    lines.append("出力形式（各記事をJSON配列で）:\n")
    lines.append('[{"id":0,"summary_ja":"〜","point":"〜","relevance":"AI/NFC/その他"},...]\n')
    lines.append("\n---\n")

    for i, article in enumerate(articles):
        title = article.get("title") or article.get("text", "")[:100] or "(タイトルなし)"
        text = article.get("text", "") or article.get("summary", "") or ""
        source = article.get("source", "")
        url = article.get("url", "")

        lines.append(f"[{i}] タイトル: {title}")
        if text and len(text) > 10:
            lines.append(f"    本文: {text[:300]}")
        if url:
            lines.append(f"    URL: {url}")
        lines.append(f"    ソース: {source}\n")

    lines.append("\n各記事について以下を含めてください:")
    lines.append("- summary_ja: 日本語要約（100〜150字）")
    lines.append("- point: なぜ重要か・何が新しいか（50字以内）")
    lines.append("- relevance: AI活用/LLM/エージェント/自動化/NFC/その他 のいずれか")

    return "\n".join(lines)


def summarize_batch(client, articles: list) -> list:
    """記事バッチをClaudeで日本語要約する"""
    prompt = build_batch_prompt(articles)

    try:
        resp = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()

        # JSON部分を抽出
        if "[" in text:
            start = text.index("[")
            end = text.rindex("]") + 1
            json_str = text[start:end]
            results = json.loads(json_str)
            return results
    except Exception as e:
        print(f"  [warn] バッチ要約エラー: {e}")

    return [{"id": i, "summary_ja": "", "point": "", "relevance": "その他"} for i in range(len(articles))]


def run(date: str = None, top_n: int = TOP_N, force: bool = False) -> dict:
    """
    処理済み記事に日本語要約を追加する

    Args:
        date: 対象日付（YYYY-MM-DD）
        top_n: 要約する上位件数
        force: 既存の要約を上書きする

    Returns:
        {'enriched': N, 'skipped': N, 'total': N}
    """
    if date is None:
        date = today_str()

    result = {"enriched": 0, "skipped": 0, "total": 0}

    processed_file = PROCESSED_DIR / date / "processed_articles.json"
    if not processed_file.exists():
        print(f"[enrich] ファイルが見つかりません: {processed_file}")
        return result

    with open(processed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        articles = data.get("items", [])
        meta = {k: v for k, v in data.items() if k != "items"}
    else:
        articles = data
        meta = {}

    result["total"] = len(articles)

    if not articles:
        print("[enrich] 記事データが空です")
        return result

    # スコア順にソートして上位N件を対象にする
    scored = sorted(
        enumerate(articles),
        key=lambda x: float(x[1].get("importance_score") or x[1].get("score") or 0),
        reverse=True
    )
    target_indices = [idx for idx, _ in scored[:top_n]]

    # 既に要約済みの記事をスキップ（forceでない場合）
    if not force:
        target_indices = [
            i for i in target_indices
            if not articles[i].get("summary_ja")
        ]

    if not target_indices:
        print(f"[enrich] 全記事に既に要約があります（force=True で上書き可）")
        return result

    print(f"[enrich] {len(target_indices)} 件を要約対象として処理します（上位{top_n}件中）")

    if anthropic is None:
        print("[enrich] anthropic がインストールされていません")
        return result

    if not ANTHROPIC_API_KEY:
        print("[enrich] ANTHROPIC_API_KEY が設定されていません")
        return result

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # バッチ処理
    for batch_start in range(0, len(target_indices), BATCH_SIZE):
        batch_indices = target_indices[batch_start:batch_start + BATCH_SIZE]
        batch_articles = [articles[i] for i in batch_indices]

        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(target_indices) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  バッチ {batch_num}/{total_batches}: {len(batch_articles)} 件処理中...")

        summaries = summarize_batch(client, batch_articles)

        for j, idx in enumerate(batch_indices):
            if j < len(summaries):
                s = summaries[j]
                articles[idx]["summary_ja"] = s.get("summary_ja", "")
                articles[idx]["point"] = s.get("point", "")
                articles[idx]["relevance"] = s.get("relevance", "その他")
                if articles[idx]["summary_ja"]:
                    result["enriched"] += 1
                    title = articles[idx].get("title") or articles[idx].get("text", "")[:40]
                    print(f"    [OK] {title[:50]}")
                else:
                    result["skipped"] += 1
            else:
                result["skipped"] += 1

        # レート制限対策
        if batch_num < total_batches:
            time.sleep(1)

    # 保存
    if isinstance(data, dict):
        data["items"] = articles
        save_data = data
    else:
        save_data = articles

    with open(processed_file, "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    print(f"\n[enrich] 完了 — 要約追加: {result['enriched']} 件 / スキップ: {result['skipped']} 件")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="記事に日本語要約を追加する")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--top-n", type=int, default=TOP_N)
    parser.add_argument("--force", action="store_true", help="既存要約を上書き")
    args = parser.parse_args()

    run(date=args.date, top_n=args.top_n, force=args.force)
