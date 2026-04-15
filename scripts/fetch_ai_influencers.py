"""
AI インフルエンサー X投稿 追跡スクリプト
Grok API を使って米国トップAIインフルエンサーの直近48時間の投稿を収集する。
APIキー未設定時は空リストを返す（モックなし）。

取得対象インフルエンサー:
  Sam Altman, Andrej Karpathy, Yann LeCun, Greg Brockman,
  Simon Willison, Swyx, Goodside, Jim Fan, Ethan Mollick, etc.

使い方:
    python scripts/fetch_ai_influencers.py
    python scripts/fetch_ai_influencers.py --hours 24
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, GROK_API_KEY, GROK_API_BASE, ensure_dirs_for_today

# 追跡するAIインフルエンサー一覧（X ハンドル → 説明）
AI_INFLUENCERS = {
    "@sama": "Sam Altman (OpenAI CEO)",
    "@karpathy": "Andrej Karpathy (ex-OpenAI, Tesla)",
    "@ylecun": "Yann LeCun (Meta Chief AI Scientist)",
    "@gdb": "Greg Brockman (OpenAI President)",
    "@fchollet": "Francois Chollet (Keras author)",
    "@DrJimFan": "Jim Fan (NVIDIA AI research lead)",
    "@emollick": "Ethan Mollick (Wharton Prof, AI educator)",
    "@simonwillison": "Simon Willison (LLM tools, Datasette)",
    "@swyx": "Swyx (AI engineer & community builder)",
    "@goodside": "Riley Goodside (Staff Prompt Engineer)",
    "@danielmiessler": "Daniel Miessler (AI security & philosophy)",
    "@AnthropicAI": "Anthropic (official)",
    "@OpenAI": "OpenAI (official)",
    "@GoogleDeepMind": "Google DeepMind (official)",
    "@huggingface": "Hugging Face (official)",
    "@scale_AI": "Scale AI (official)",
    "@skirano": "Pietro Schirano (Figma / AI design)",
    "@bentossell": "Ben Tossell (no-code AI tools)",
}

BATCH_SIZE = 6  # 1回のGrok API呼び出しで検索するインフルエンサー数


def _build_influencer_prompt(handles: list[str], hours: int) -> str:
    handles_str = ", ".join(handles)
    return f"""You are an AI news researcher tracking top AI influencers on X (Twitter).

Search for recent posts (within the last {hours} hours) from these accounts: {handles_str}

For each account that posted recently, return their most notable post(s) about AI, LLM, agents, tools, or tech.

Return a JSON array. Each item should have:
- "id": unique string (format: "inf_{{handle}}_{{index}}")
- "author": X handle (e.g. "@sama")
- "author_name": full name
- "text": the post content in original language (max 300 chars)
- "text_ja": Japanese translation/summary (100-150 chars)
- "likes": estimated likes (integer)
- "retweets": estimated retweets (integer)
- "posted_hours_ago": approximate hours ago posted (integer)
- "topic": main topic keyword (e.g. "Claude", "GPT-5", "AI Agents", "LLM")
- "importance": score 1-5 (5 = major announcement or viral)
- "source": "x_influencer"

Only include posts that are actually about AI/tech topics (skip sports, politics, etc.).
If an account has no recent AI posts, skip it.
Return ONLY the JSON array, no explanation."""


def fetch_influencer_posts(hours: int = 48) -> list[dict]:
    """Grok API でインフルエンサーの直近投稿を取得する"""
    if not GROK_API_KEY:
        print("[INFLUENCERS] GROK_API_KEY未設定 → スキップ")
        return []

    print(f"[INFLUENCERS] {len(AI_INFLUENCERS)} アカウントを{hours}時間以内で検索...")

    all_posts = []
    handles = list(AI_INFLUENCERS.keys())

    # バッチ処理でAPIコール数を削減
    for i in range(0, len(handles), BATCH_SIZE):
        batch = handles[i:i + BATCH_SIZE]
        print(f"  バッチ {i // BATCH_SIZE + 1}: {', '.join(batch)}")

        try:
            posts = _call_grok(batch, hours)
            all_posts.extend(posts)
            print(f"  → {len(posts)} 件取得")
        except Exception as e:
            print(f"  → エラー: {e}")
            continue

    # 重複除去 + 重要度順ソート
    seen_ids = set()
    unique_posts = []
    for post in all_posts:
        pid = post.get("id", "")
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_posts.append(post)

    unique_posts.sort(key=lambda x: (x.get("importance", 0), x.get("likes", 0)), reverse=True)

    print(f"[INFLUENCERS] 合計 {len(unique_posts)} 件取得（{len(AI_INFLUENCERS)} アカウント対象）")
    return unique_posts


def _call_grok(handles: list[str], hours: int) -> list[dict]:
    """Grok API を呼び出す（リアルタイムX検索有効）"""
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    prompt = _build_influencer_prompt(handles, hours)

    # @を除いたハンドル名リスト（xAI search_parameters用）
    clean_handles = [h.lstrip("@") for h in handles]

    payload = {
        "model": "grok-4-1-fast-non-reasoning",
        "messages": [
            {
                "role": "system",
                "content": "You are an AI news researcher. Always respond with valid JSON arrays only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        # Agent Tools API でリアルタイムX検索（search_parameters は廃止済み）
        "tools": [{"type": "x_search"}],
    }

    response = requests.post(
        f"{GROK_API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=45,
    )
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"].strip()

    # コードブロック除去
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0]

    posts = json.loads(content)

    # バリデーション + 正規化
    validated = []
    for p in posts:
        if not isinstance(p, dict):
            continue
        author_handle = str(p.get("author", "@unknown"))
        if not author_handle.startswith("@"):
            author_handle = f"@{author_handle}"
        # author_name が空の場合は AI_INFLUENCERS の説明文からフォールバック
        raw_name = str(p.get("author_name", "") or "").strip()
        if not raw_name:
            desc = AI_INFLUENCERS.get(author_handle.lower(), "") or AI_INFLUENCERS.get(author_handle, "")
            raw_name = desc.split("(")[0].strip() if desc else author_handle
        validated.append({
            "id": str(p.get("id", f"inf_{len(validated)}")),
            "author": author_handle,
            "author_name": raw_name,
            "text": str(p.get("text", ""))[:500],
            "text_ja": str(p.get("text_ja", ""))[:300],
            "title": f"[{p.get('author', '')}] {str(p.get('text', ''))[:80]}",
            "likes": int(p.get("likes", 0)),
            "retweets": int(p.get("retweets", 0)),
            "posted_hours_ago": int(p.get("posted_hours_ago", 48)),
            "topic": str(p.get("topic", "AI")),
            "importance": int(p.get("importance", 1)),
            "source": "x_influencer",
            "fetched_at": datetime.now().isoformat(),
        })
    return validated


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "ai_influencers_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "fetched_at": datetime.now().isoformat(),
                "count": len(posts),
                "influencers_tracked": list(AI_INFLUENCERS.keys()),
                "posts": posts,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[INFLUENCERS] 保存: {filepath}")
    return filepath


def run(hours: int = 48) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = fetch_influencer_posts(hours)
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI influencer posts from X via Grok")
    parser.add_argument("--hours", type=int, default=48, help="Hours to look back (default: 48)")
    args = parser.parse_args()
    results = run(args.hours)
    print(f"\n=== Results: {len(results)} posts from AI influencers ===")
    for p in results[:10]:
        print(f"  [{p['author']} ♥{p['likes']}] [{p['topic']}] {p['text'][:80]}...")
