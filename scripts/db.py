"""
Supabase ヘルパーモジュール

提供する機能:
  - Supabase クライアントシングルトン
  - canonical_key / normalized_url 生成
  - articles upsert（初回INSERT + 再取得UPDATE）
  - article_delivery_states 初期化・更新
  - pipeline_runs 作成・完了
  - x_drafts 挿入
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

try:
    from supabase import create_client
except ImportError:
    create_client = None

import sys
sys.path.insert(0, str(Path(__file__).parent))
from config import SUPABASE_URL, SUPABASE_KEY, LATEST_DIR

# URLから除去するトラッキング系クエリパラメータ
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_reader", "utm_name",
    "fbclid", "gclid", "gad_source", "gbraid", "wbraid",
    "ref", "source", "mc_cid", "mc_eid", "igshid",
    "_hsenc", "_hsmi", "yclid", "msclkid",
})

_client = None
_CURRENT_RUN_FILE = LATEST_DIR / "current_run.json"


# ── クライアント ──────────────────────────────────────────────────────────────

def get_supabase():
    """
    Supabase クライアントを返す。
    SUPABASE_URL / SUPABASE_KEY が未設定の場合は None を返す（全関数がno-opになる）。
    """
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return None
    _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ── canonical_key 生成 ────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """
    URLを正規化する。
      1. scheme + host を小文字化
      2. トラッキング系クエリパラメータを除去
      3. path の trailing slash を除去
      4. fragment を除去
    """
    url = url.strip()
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        new_query = urlencode(sorted((k, v[0]) for k, v in filtered.items()))
        return urlunparse((scheme, netloc, path, "", new_query, ""))
    except Exception:
        return url.lower().strip()


def generate_canonical_key(
    url: str = "",
    source: str = "",
    title: str = "",
) -> tuple[str, str]:
    """
    (canonical_key, normalized_url) を返す。

    URL あり: SHA256(normalized_url)[:24]  ※96bit、日次数千件規模で衝突確率は無視できる水準
    URL なし: SHA256(lower(source) + '|' + lower(title[:120]))[:24]
    """
    if url and url.startswith("http"):
        normalized = normalize_url(url)
        key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
        return key, normalized
    fallback = f"{source.lower()}|{title.lower()[:120]}"
    key = hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:24]
    return key, ""


# ── pipeline_runs ─────────────────────────────────────────────────────────────

def create_pipeline_run(
    supabase,
    run_date: str,
    trigger_type: str = "cron",
    parent_run_id: str | None = None,
) -> str | None:
    """
    pipeline_runs に新規ランを INSERT し run_id を返す。
    同時に outputs/latest/current_run.json に保存する（後続スクリプト参照用）。
    """
    if supabase is None:
        return None
    try:
        payload = {
            "run_date": run_date,
            "trigger_type": trigger_type,
            "status": "running",
        }
        if parent_run_id:
            payload["parent_run_id"] = parent_run_id

        resp = supabase.table("pipeline_runs").insert(payload).execute()
        run_id = resp.data[0]["id"]

        LATEST_DIR.mkdir(parents=True, exist_ok=True)
        _CURRENT_RUN_FILE.write_text(
            json.dumps({"run_id": run_id, "run_date": run_date}),
            encoding="utf-8",
        )
        print(f"[db] pipeline_run 作成: {run_id[:8]}...")
        return run_id
    except Exception as e:
        print(f"[db] pipeline_run 作成失敗: {e}")
        return None


def close_pipeline_run(
    supabase,
    run_id: str,
    status: str = "success",
    **stats,
) -> None:
    """pipeline_run を完了状態に更新する。"""
    if supabase is None or not run_id:
        return
    try:
        payload = {
            "status": status,
            "finished_at": _now_iso(),
        }
        for k, v in stats.items():
            if v is not None:
                payload[k] = v
        supabase.table("pipeline_runs").update(payload).eq("id", run_id).execute()
        print(f"[db] pipeline_run 完了: {run_id[:8]}... ({status})")
    except Exception as e:
        print(f"[db] pipeline_run 更新失敗: {e}")


def get_current_run_id(run_date: str) -> str | None:
    """
    current_run.json から当日の run_id を取得する。
    ファイルがない、または日付が異なる場合は None を返す。
    """
    try:
        if _CURRENT_RUN_FILE.exists():
            data = json.loads(_CURRENT_RUN_FILE.read_text(encoding="utf-8"))
            if data.get("run_date") == run_date:
                return data.get("run_id")
    except Exception:
        pass
    return None


# ── articles upsert ───────────────────────────────────────────────────────────

def upsert_article(supabase, item: dict, run_date: str) -> str | None:
    """
    articles に upsert し article_id を返す。

    初回 INSERT:
      - 全フィールドを INSERT
      - article_delivery_states を初期化（block_history に初期ブロックを記録）

    再取得 UPDATE:
      - first_seen_date / fetched_at は変更しない
      - last_seen_date / seen_count / スコア / summary_ja / raw_data を更新
      - output_block が変化した場合のみ delivery_states.block_history を APPEND する
    """
    if supabase is None:
        return None

    url = item.get("url") or ""
    source = item.get("source") or ""
    title = item.get("title") or ""
    canonical_key, normalized_url = generate_canonical_key(url, source, title)
    new_block = item.get("output_block")

    try:
        existing_resp = (
            supabase.table("articles")
            .select("id, output_block, first_seen_date, seen_count")
            .eq("canonical_key", canonical_key)
            .execute()
        )
        existing = existing_resp.data[0] if existing_resp.data else None

        if existing:
            # ── UPDATE ──────────────────────────────────────────────
            article_id = existing["id"]
            old_block = existing.get("output_block")
            seen_count = (existing.get("seen_count") or 1) + 1

            update_payload = {
                "last_seen_date": run_date,
                "seen_count": seen_count,
                "lane": item.get("lane"),
                "frontier_score": item.get("frontier_score"),
                "proposal_score": item.get("proposal_score"),
                "output_block": new_block,
                "importance_score": item.get("importance_score"),
                "summary_ja": item.get("summary_ja"),
                "topic": item.get("topic"),
                "raw_data": item,
            }
            if item.get("published_at"):
                update_payload["published_at"] = item["published_at"]

            supabase.table("articles").update(update_payload).eq("id", article_id).execute()

            # block が変化した場合のみ delivery_state を更新
            if new_block and new_block != old_block:
                _append_block_history(supabase, article_id, new_block, run_date)

            return article_id

        else:
            # ── INSERT ──────────────────────────────────────────────
            insert_payload = {
                "canonical_key": canonical_key,
                "normalized_url": normalized_url,
                "url": url,
                "first_seen_date": run_date,
                "last_seen_date": run_date,
                "seen_count": 1,
                "title": title,
                "source": source,
                "lang": item.get("lang"),
                "topic": item.get("topic"),
                "summary_ja": item.get("summary_ja"),
                "published_at": item.get("published_at"),
                "fetched_at": _now_iso(),
                "raw_data": item,
                "lane": item.get("lane"),
                "frontier_score": item.get("frontier_score"),
                "proposal_score": item.get("proposal_score"),
                "output_block": new_block,
                "importance_score": item.get("importance_score"),
            }
            resp = supabase.table("articles").insert(insert_payload).execute()
            article_id = resp.data[0]["id"]

            _init_delivery_state(supabase, article_id, new_block, run_date)
            return article_id

    except Exception as e:
        print(f"[db] article upsert 失敗 ({canonical_key[:12]}...): {e}")
        return None


def _init_delivery_state(
    supabase,
    article_id: str,
    initial_block: str | None,
    run_date: str,
) -> None:
    """article_delivery_states の初期行を INSERT する。"""
    try:
        payload: dict = {"article_id": article_id}
        if initial_block:
            payload["block_history"] = [{"block": initial_block, "scored_at": run_date}]
            payload["last_block"] = initial_block
        supabase.table("article_delivery_states").insert(payload).execute()
    except Exception as e:
        print(f"[db] delivery_state 初期化失敗 ({article_id[:8]}...): {e}")


def _append_block_history(
    supabase,
    article_id: str,
    new_block: str,
    run_date: str,
) -> None:
    """
    output_block が変化した場合のみ block_history に追記し、last_block を更新する。
    """
    try:
        resp = (
            supabase.table("article_delivery_states")
            .select("block_history")
            .eq("article_id", article_id)
            .execute()
        )
        if not resp.data:
            _init_delivery_state(supabase, article_id, new_block, run_date)
            return

        current_history = resp.data[0].get("block_history") or []
        new_history = list(current_history) + [{"block": new_block, "scored_at": run_date}]

        supabase.table("article_delivery_states").update({
            "block_history": new_history,
            "last_block": new_block,
        }).eq("article_id", article_id).execute()
    except Exception as e:
        print(f"[db] block_history 追記失敗 ({article_id[:8]}...): {e}")


# ── delivery state 更新 ───────────────────────────────────────────────────────

def update_telegram_state(
    supabase,
    article_id: str,
    run_id: str | None,
    telegram_block: str,
) -> None:
    """Telegram 送信済みを article_delivery_states に記録する。"""
    if supabase is None or not article_id:
        return
    try:
        now = _now_iso()
        supabase.table("article_delivery_states").update({
            "sent_to_telegram_at": now,
            "telegram_run_id": run_id,
            "telegram_block": telegram_block,
            "last_notified_at": now,
        }).eq("article_id", article_id).execute()
    except Exception as e:
        print(f"[db] telegram_state 更新失敗 ({article_id[:8]}...): {e}")


def update_notion_state(
    supabase,
    article_id: str,
    run_id: str | None,
    notion_page_id: str,
) -> None:
    """Notion 保存済みを article_delivery_states に記録する。"""
    if supabase is None or not article_id:
        return
    try:
        now = _now_iso()
        supabase.table("article_delivery_states").update({
            "saved_to_notion_at": now,
            "notion_run_id": run_id,
            "notion_page_id": notion_page_id,
            "last_notified_at": now,
        }).eq("article_id", article_id).execute()
    except Exception as e:
        print(f"[db] notion_state 更新失敗 ({article_id[:8]}...): {e}")


# ── x_drafts 挿入 ─────────────────────────────────────────────────────────────

def insert_x_draft(
    supabase,
    draft: dict,
    run_id: str | None,
    article_id: str | None = None,
) -> None:
    """x_drafts に1件挿入する。"""
    if supabase is None:
        return
    try:
        supabase.table("x_drafts").insert({
            "run_id": run_id,
            "article_id": article_id,
            "draft_text": draft.get("draft_text", ""),
            "style_label": draft.get("style_label"),
            "urgency": draft.get("urgency"),
            "key_insight": draft.get("key_insight"),
            "char_count": draft.get("char_count") or len(draft.get("draft_text", "")),
            "generated_by": draft.get("generated_by"),
        }).execute()
    except Exception as e:
        print(f"[db] x_draft 挿入失敗: {e}")


# ── 内部ユーティリティ ────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
