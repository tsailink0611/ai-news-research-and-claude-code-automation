"""
X投稿 3エージェント生成パイプライン

リサーチャー → ライター → エディターの3段階で高品質なX投稿文を生成する。

エージェント構成:
  Researcher : 記事の核心・文脈・投稿角度を分析（バッチ1回）
  Writer     : 分析を元に投稿文の初稿を生成（バッチ1回）
  Editor     : 全ドラフトを統一感・自然さで仕上げ（バッチ1回）

合計 Claude API 呼び出し: 3回（記事数に依存しない）
"""
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, X_CHAR_LIMIT,
    DRAFT_STYLES, ANTHROPIC_API_KEY, CLAUDE_MODEL,
    ensure_dirs_for_today, today_str
)

TOP_N_FOR_X = 10  # X向けに絞る記事数


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


def _pick_urgency(score: float) -> str:
    if score >= 5.0:
        return "high"
    if score >= 3.0:
        return "medium"
    return "low"


def _recommended_use(angle: str, urgency: str) -> str:
    if urgency == "high":
        return "即時投稿推奨"
    map_ = {
        "解説": "教育・価値提供向け",
        "実務": "エンゲージメント重視",
        "比較": "議論喚起向け",
        "速報": "タイムリー投稿",
    }
    return map_.get(angle, "通常スケジュール投稿")


# ───────────────────────────────────────────────────────────────
# Agent 1: Researcher
# 役割: 各記事の「何が重要か」「なぜ今か」「どう伝えるか」を分析する
# ───────────────────────────────────────────────────────────────

def run_researcher(client, items: list[dict]) -> list[dict]:
    """
    記事リストを一括分析し、各記事の投稿戦略を返す。
    出力: [{key_insight, context, angle, hook, tags}, ...]
    """
    print(f"[Researcher] {len(items)} 件を分析中...")

    articles_text = ""
    for i, item in enumerate(items):
        title = item.get("title") or ""
        summary = item.get("summary_ja") or item.get("summary") or item.get("point") or ""
        source = item.get("source") or ""
        score = item.get("importance_score", 0)
        articles_text += (
            f"\n[{i}]\n"
            f"タイトル: {title}\n"
            f"要約: {summary[:200]}\n"
            f"ソース: {source} | スコア: {score}\n"
        )

    prompt = f"""あなたはAI・テクノロジー分野の記事分析の専門家です。
以下の記事リストを読み、X（旧Twitter）投稿に最適な切り口を分析してください。

## 分析対象記事
{articles_text}

## 各記事について以下を返してください
- key_insight: この記事で最も重要な事実・数値・発見（30文字以内）
- context: なぜ今これが重要か、何が変わるのか（40文字以内）
- angle: 投稿の切り口（「解説」「実務」「比較」「速報」から1つ）
- hook: 読者が思わず止まる書き出し案（体言止めか問いかけ、25文字以内）
- tags: おすすめハッシュタグ 2〜3個（#付き、スペース区切り）

## 出力形式（JSONのみ、説明不要）
[
  {{"index": 0, "key_insight": "...", "context": "...", "angle": "...", "hook": "...", "tags": "..."}},
  ...
]"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        analyses = json.loads(content)
        print(f"[Researcher] {len(analyses)} 件の分析完了")
        return analyses
    except Exception as e:
        print(f"[Researcher] エラー: {e}")
        return [{"index": i, "key_insight": "", "context": "", "angle": "速報", "hook": "", "tags": "#AI"} for i in range(len(items))]


# ───────────────────────────────────────────────────────────────
# Agent 2: Writer
# 役割: Researcher の分析を元に投稿文の初稿を生成する
# ───────────────────────────────────────────────────────────────

def run_writer(client, items: list[dict], analyses: list[dict]) -> list[dict]:
    """
    記事 + 分析結果を元に X 投稿の初稿を一括生成する。
    出力: [{index, draft_text}, ...]
    """
    print(f"[Writer] {len(items)} 本の初稿を生成中...")

    input_text = ""
    for a in analyses:
        idx = a.get("index", 0)
        item = items[idx] if idx < len(items) else {}
        title = item.get("title") or ""
        input_text += (
            f"\n[{idx}]\n"
            f"タイトル: {title}\n"
            f"核心: {a.get('key_insight', '')}\n"
            f"文脈: {a.get('context', '')}\n"
            f"切り口: {a.get('angle', '')}\n"
            f"書き出し案: {a.get('hook', '')}\n"
            f"タグ案: {a.get('tags', '#AI')}\n"
        )

    prompt = f"""あなたは「AIの最前線を先に触り、中小企業に落とし込む専門家」の視点でX投稿を書くライターです。
読者は中小企業の経営者・経営幹部。技術詳細より「自分のビジネスにどう関係するか」を求めています。

以下の記事分析を元に、X投稿文の初稿を生成してください。

## 記事・分析データ
{input_text}

## 投稿の方針
- 切り口が「frontier（先端）」の記事: 「これが3〜6ヶ月後に国内に来る」という先読みコンサル視点で書く
- 切り口が「実務・解説」の記事: 「同業他社がすでにやっている」という現実感・比較視点で書く
- 切り口が「比較」の記事: 選択肢とその判断基準を経営者目線で整理する
- 読んだ経営者が「うちはどうだろう？」と思わせることがゴール

## 文体ルール
- 140〜200文字（URLは含めない）
- ハッシュタグは末尾に2〜3個（#AI 必須）
- 「です・ます」調。語尾は全て同じにしない
- 具体的な事実・数値・固有名詞を1つ以上入れる
- 禁止: 「画期的」「革新的」「注目」「必見」「衝撃」「〜ですね」「〜してみた」「【速報】等ブラケット」「絵文字」
- 書き出しを毎回変える（体言止め・問いかけ・状況描写などを混在させる）

## 出力形式（JSONのみ）
[{{"index": 0, "draft_text": "投稿文"}}, ...]"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        drafts = json.loads(content)
        print(f"[Writer] {len(drafts)} 本の初稿完成")
        return drafts
    except Exception as e:
        print(f"[Writer] エラー: {e}")
        return [{"index": i, "draft_text": (items[i].get("title") or "")[:100] + "\n#AI"} for i in range(len(items))]


# ───────────────────────────────────────────────────────────────
# Agent 3: Editor
# 役割: 全ドラフトを読み比べ、語尾・書き出し・文体の単調さを直し仕上げる
# ───────────────────────────────────────────────────────────────

def run_editor(client, drafts: list[dict]) -> list[dict]:
    """
    全初稿を一括でレビューし、最終版に仕上げる。
    出力: [{index, draft_text}, ...]
    """
    print(f"[Editor] {len(drafts)} 本を最終仕上げ中...")

    drafts_text = ""
    for d in drafts:
        drafts_text += f"\n[{d['index']}]\n{d.get('draft_text', '')}\n"

    prompt = f"""あなたは「AIの最前線を先に触り、中小企業に落とし込む専門家」として活動するコンサルタントのX投稿編集者です。
以下の初稿を読み比べ、このペルソナで書いた文体に仕上げてください。

## チェック・修正ポイント
1. 全10本の書き出しが単調でないか（同じ書き出しパターンが3本以上あれば直す）
2. 語尾のバリエーション（「〜です」「〜ます」「〜でしょう」「〜から」等を自然に混在させる）
3. 内容の薄いドラフトに具体性を足す（数値・固有名詞・具体的な用途など）
4. 文字数が140文字未満なら情報を足す。200文字超なら削る
5. ハッシュタグは末尾2〜3個のみ（#AI は必須）
6. 禁止表現の最終確認: 「画期的」「革新的」「注目」「必見」「〜ですね」「〜してみた」

## 方針
- 内容の本質は変えない。表現と構造のみ調整する
- 「これが3〜6ヶ月後に国内に来る」「同業他社がすでにやっている」という先読み・現実感が出ているか確認する
- 経営者が「うちはどうだろう？」と自問するような具体性・実業感のある文体に整える
- AIが書いた感を排除し、DX・AI導入の現場を知っているコンサルタントが書いた文体にする
- 10本全体を1人のコンサルタントが書いたように統一する

## 初稿
{drafts_text}

## 出力形式（JSONのみ）
[{{"index": 0, "draft_text": "最終テキスト"}}, ...]"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        final = json.loads(content)
        print(f"[Editor] {len(final)} 本の最終版完成")
        return final
    except Exception as e:
        print(f"[Editor] エラー: {e}（Writerの初稿をそのまま使用）")
        return drafts


# ───────────────────────────────────────────────────────────────
# フォールバック（API なし）
# ───────────────────────────────────────────────────────────────

def _fallback_drafts(items: list[dict]) -> list[dict]:
    """Claude APIなし時のテンプレート生成"""
    results = []
    for i, item in enumerate(items):
        title = item.get("title") or ""
        point = item.get("point") or item.get("summary_ja") or ""
        topic = item.get("topic", "AI").replace(" ", "")
        text = point if point else title[:100]
        results.append({
            "index": i,
            "draft_text": f"{text[:150]}\n#AI #{topic}"
        })
    return results


# ───────────────────────────────────────────────────────────────
# 統合・保存
# ───────────────────────────────────────────────────────────────

def summarize_all(date: str) -> list[dict]:
    """3エージェントパイプラインを実行し、X投稿ドラフトを返す"""
    data = load_processed(date)
    if not data:
        print(f"[X-SUMMARY] データなし: {date}")
        return []

    items = data.get("items", [])
    items = sorted(items, key=lambda x: x.get("importance_score", 0), reverse=True)
    items = items[:TOP_N_FOR_X]

    print(f"\n[X-SUMMARY] 3エージェントパイプライン開始（{len(items)} 件）")

    client = _get_claude_client()

    if not client:
        print("[X-SUMMARY] APIキーなし → テンプレート生成")
        final_drafts = _fallback_drafts(items)
        analyses = [{"index": i, "angle": "速報", "tags": "#AI"} for i in range(len(items))]
    else:
        print(f"[X-SUMMARY] モデル: {CLAUDE_MODEL}")

        # Agent 1: Researcher
        analyses = run_researcher(client, items)

        # Agent 2: Writer
        writer_drafts = run_writer(client, items, analyses)

        # Agent 3: Editor
        final_drafts = run_editor(client, writer_drafts)

    # 分析結果とドラフトをマージして summaries を構築
    analysis_map = {a.get("index", i): a for i, a in enumerate(analyses)}
    draft_map = {d.get("index", i): d for i, d in enumerate(final_drafts)}

    summaries = []
    for i, item in enumerate(items):
        analysis = analysis_map.get(i, {})
        draft = draft_map.get(i, {})

        text = draft.get("draft_text") or (item.get("title") or "")[:100] + "\n#AI"
        text = text[:X_CHAR_LIMIT]
        score = item.get("importance_score", 0)
        angle = analysis.get("angle", "速報")
        urgency = _pick_urgency(score)

        summaries.append({
            "topic": item.get("topic", "AI"),
            "source_type": item.get("source", "unknown"),
            "style": angle,
            "style_label": angle,
            "urgency": urgency,
            "recommended_use": _recommended_use(angle, urgency),
            "draft_text": text,
            "char_count": len(text),
            "original_title": item.get("title") or "",
            "importance_score": score,
            "key_insight": analysis.get("key_insight", ""),
            "context": analysis.get("context", ""),
            "generated_by": "3-agent-pipeline" if client else "template",
        })
        print(f"  [{i+1}/{len(items)}] [{angle}] {(item.get('title') or '')[:40]}")

    print(f"\n[X-SUMMARY] {len(summaries)} 件生成完了（3エージェント）")
    return summaries


def save_summaries(summaries: list[dict], date: str) -> Path:
    filepath = DAILY_DIR / date / "x_summaries.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "date": date,
            "generated_at": datetime.now().isoformat(),
            "count": len(summaries),
            "pipeline": "researcher → writer → editor",
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
    print(f"\n=== {len(results)} summaries (3-agent pipeline) ===")
    for s in results[:5]:
        print(f"  [{s['style_label']}] {s['draft_text'][:80]}...")
