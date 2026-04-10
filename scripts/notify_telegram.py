"""
Telegram通知スクリプト
パイプラインの結果をTelegram Botで自分に送信する。
ダイジェスト・注目記事TOP5・Xドラフト候補をプッシュ通知。

準備:
    1. @BotFather でBotを作成 → トークンを取得
    2. Botに /start を送る
    3. TELEGRAM_BOT_TOKEN と TELEGRAM_CHAT_ID を .env に設定

使い方:
    python scripts/notify_telegram.py             # 今日の結果を送信
    python scripts/notify_telegram.py --date 2026-04-06
    python scripts/notify_telegram.py --test       # 接続テスト
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    PROCESSED_DIR, DAILY_DIR, LATEST_DIR, X_DRAFTS_DIR,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ensure_dirs_for_today, today_str,
)
from db import get_supabase, update_telegram_state, get_current_run_id

TELEGRAM_API = "https://api.telegram.org/bot{token}"
MAX_MESSAGE_LENGTH = 4096  # Telegram の1メッセージ上限


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Telegram にメッセージを送信する"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] ERROR: TELEGRAM_BOT_TOKEN と TELEGRAM_CHAT_ID を .env に設定してください")
        return False

    url = f"{TELEGRAM_API.format(token=TELEGRAM_BOT_TOKEN)}/sendMessage"

    # 長すぎるメッセージは分割送信
    chunks = _split_message(text, MAX_MESSAGE_LENGTH)

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                print(f"[TELEGRAM] Send failed: {result.get('description', 'unknown error')}")
                return False
        except Exception as e:
            print(f"[TELEGRAM] Error: {e}")
            return False

    return True


def _split_message(text: str, max_len: int) -> list[str]:
    """メッセージを上限以内に分割する"""
    if len(text) <= max_len:
        return [text]

    chunks = []
    lines = text.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)

    return chunks


def build_digest_message(date: str) -> str | None:
    """Block A/B/C 形式のダイジェストメッセージを構築する"""
    processed_path = PROCESSED_DIR / date / "processed_articles.json"
    if not processed_path.exists():
        return None

    with open(processed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    stats = data.get("stats", {})
    sources = stats.get("sources", [])

    # ブロック別に分類
    block_a = [i for i in items if i.get("output_block") == "A"]
    block_b = [i for i in items if i.get("output_block") == "B"]
    block_c = [i for i in items if i.get("output_block") == "C"]

    # P軸・F軸でそれぞれソート
    block_a.sort(key=lambda x: x.get("proposal_score", 0), reverse=True)
    block_b.sort(key=lambda x: x.get("frontier_score", 0), reverse=True)

    lines = []
    lines.append(f"<b>案件化支援OS  {date}</b>")
    lines.append(f"<code>{len(items)} 件収集 | A:{len(block_a)} B:{len(block_b)} C:{len(block_c)}</code>")

    # ── Block A: 今すぐ提案ネタ ──────────────────────────────
    lines.append("")
    lines.append("<b>Block A — 今すぐ提案ネタ</b>")
    if block_a:
        for i, item in enumerate(block_a[:3], 1):
            title = _escape_html((item.get("title") or "")[:60])
            p = item.get("proposal_score", 0)
            f = item.get("frontier_score", 0)
            source = item.get("source", "")
            point = item.get("summary_ja") or item.get("point") or ""
            url = item.get("url", "")

            lines.append(f"\n<b>{i}. {title}</b>")
            lines.append(f"   P:{p}  F:{f}  |  {source}")
            if point:
                lines.append(f"   <i>{_escape_html(point[:90])}</i>")
            if url and url.startswith("http"):
                lines.append(f"   <a href=\"{url}\">記事を読む</a>")
    else:
        lines.append("   <i>今日は該当なし（P≥5の記事なし）</i>")

    # ── Block B: 今週触るべき先端シグナル ───────────────────
    lines.append("")
    lines.append("<b>Block B — 今週触るべき先端シグナル</b>")
    if block_b:
        for i, item in enumerate(block_b[:3], 1):
            title = _escape_html((item.get("title") or "")[:60])
            p = item.get("proposal_score", 0)
            f = item.get("frontier_score", 0)
            source = item.get("source", "")
            point = item.get("summary_ja") or item.get("point") or ""
            url = item.get("url", "")

            lines.append(f"\n<b>{i}. {title}</b>")
            lines.append(f"   F:{f}  P:{p}  |  {source}")
            if point:
                lines.append(f"   <i>{_escape_html(point[:90])}</i>")
            if url and url.startswith("http"):
                lines.append(f"   <a href=\"{url}\">記事を読む</a>")
    else:
        lines.append("   <i>今日は該当なし（F≥6かつP≥2の記事なし）</i>")

    # ── Block C: 将来ネタ保存（件数のみ） ────────────────────
    lines.append("")
    lines.append("<b>Block C — 将来ネタ保存</b>")
    if block_c:
        # カテゴリ別集計
        cat_count: dict[str, int] = {}
        for item in block_c:
            lane = item.get("lane", "frontier")
            cat_count[lane] = cat_count.get(lane, 0) + 1
        detail = "  ".join(f"{k}:{v}件" for k, v in cat_count.items())
        lines.append(f"   Notionに {len(block_c)} 件を保存  |  {detail}")
    else:
        lines.append("   <i>なし</i>")

    return "\n".join(lines)


def build_drafts_message(date: str) -> str | None:
    """Xドラフト通知メッセージを構築する"""
    drafts_path = LATEST_DIR / "latest_x_drafts.json"
    if not drafts_path.exists():
        return None

    with open(drafts_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    drafts = data.get("drafts", [])
    if not drafts:
        return None

    lines = []
    lines.append(f"<b>X 投稿ドラフト  {len(drafts)} 本</b>")
    lines.append("")

    # 緊急度高 → 中 の順で最大5本表示
    high = [d for d in drafts if d.get("urgency") == "high"]
    medium = [d for d in drafts if d.get("urgency") == "medium"]
    show_drafts = (high + medium)[:5]

    urgency_label = {"high": "急", "medium": "推", "low": ""}

    for i, draft in enumerate(show_drafts, 1):
        urgency = urgency_label.get(draft.get("urgency", ""), "")
        style = draft.get("style_label", "")
        text = _escape_html(draft.get("draft_text", "")[:220])

        label = f"[{urgency}]" if urgency else ""
        lines.append(f"<b>#{i} {label} {style}</b>")
        lines.append(f"{text}")
        lines.append("")

    if len(drafts) > len(show_drafts):
        lines.append(f"<i>他 {len(drafts) - len(show_drafts)} 本は Notion で確認できます</i>")

    return "\n".join(lines)


def build_influencer_message(date: str) -> str | None:
    """AIインフルエンサーの直近投稿ハイライトを構築する"""
    influencer_path = Path(__file__).parent.parent / "data" / "raw" / date / "ai_influencers_raw.json"
    if not influencer_path.exists():
        return None

    try:
        with open(influencer_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    posts = data.get("posts", [])
    if not posts:
        return None

    # 重要度5 → 4 → いいね数の順で上位5件
    posts = sorted(posts, key=lambda x: (x.get("importance", 0), x.get("likes", 0)), reverse=True)
    top = posts[:5]

    lines = []
    lines.append(f"<b>AI インフルエンサー速報 (48h)  {len(posts)} 件</b>")
    lines.append("")

    for i, post in enumerate(top, 1):
        author = _escape_html(post.get("author", ""))
        topic = _escape_html(post.get("topic", ""))
        imp = post.get("importance", 1)
        likes = post.get("likes", 0)
        text_ja = _escape_html(post.get("text_ja", "") or post.get("text", "")[:100])
        hours_ago = post.get("posted_hours_ago", "?")
        stars = "★" * min(imp, 5)

        lines.append(f"<b>{i}. {author}</b>  {stars}  {likes:,}♥  {hours_ago}h前")
        lines.append(f"   [{topic}] {text_ja[:120]}")
        lines.append("")

    return "\n".join(lines)


def build_summary_message(date: str) -> str | None:
    """コンパクトサマリーを構築する（--compact オプション用）"""
    processed_path = PROCESSED_DIR / date / "processed_articles.json"
    if not processed_path.exists():
        return None

    with open(processed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    topics = data.get("topics", [])
    stats = data.get("stats", {})
    sources = stats.get("sources", [])

    lines = []
    lines.append(f"<b>AI News  {date}</b>")
    lines.append(f"<code>{len(items)} 件  |  {len(sources)} ソース</code>")
    lines.append("")

    lines.append("<b>トピック</b>")
    for topic in topics[:3]:
        lines.append(f"  <b>{_escape_html(topic['topic'])}</b>  {topic['count']}件")

    lines.append("")
    lines.append("<b>注目記事</b>")
    for i, item in enumerate(items[:3], 1):
        title = _escape_html((item.get("title") or item.get("text", ""))[:60])
        lines.append(f"{i}. {title}")

    return "\n".join(lines)


def _escape_html(text: str) -> str:
    """Telegram HTML用エスケープ"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_test() -> bool:
    """接続テスト"""
    text = (
        "<b>AI News Bot - Connection Test</b>\n\n"
        "Telegram Bot is working!\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    success = send_message(text)
    if success:
        print("[TELEGRAM] Test message sent successfully!")
    return success


def _update_telegram_delivery_state(supabase, date: str, run_id: str | None) -> None:
    """Telegramに送信したBlock A/B記事のdelivery_stateを更新する"""
    processed_path = PROCESSED_DIR / date / "processed_articles.json"
    if not processed_path.exists():
        return
    try:
        with open(processed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        for item in items:
            block = item.get("output_block")
            if block not in ("A", "B"):
                continue
            article_id = item.get("supabase_id")
            if article_id:
                update_telegram_state(supabase, article_id, run_id, block)
    except Exception as e:
        print(f"[TELEGRAM] delivery_state 更新失敗: {e}")


def notify(date: str | None = None, compact: bool = False) -> bool:
    """パイプライン結果をTelegramに送信する"""
    if date is None:
        date = today_str()

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        return False

    supabase = get_supabase()
    run_id = get_current_run_id(date)

    print(f"[TELEGRAM] Sending notifications for {date}...")

    if compact:
        # コンパクト版: 1メッセージのみ
        msg = build_summary_message(date)
        if msg:
            return send_message(msg)
        print("[TELEGRAM] No data to send")
        return False

    # フル版: インフルエンサー速報 + ダイジェスト + ドラフト候補
    success = True

    influencer_msg = build_influencer_message(date)
    if influencer_msg:
        if send_message(influencer_msg):
            print("[TELEGRAM] Influencer highlights sent")
        else:
            success = False

    digest_msg = build_digest_message(date)
    if digest_msg:
        if send_message(digest_msg):
            print("[TELEGRAM] Digest sent")
            # Telegramに送信したBlock A/Bの記事のdelivery_stateを更新する
            _update_telegram_delivery_state(supabase, date, run_id)
        else:
            success = False

    drafts_msg = build_drafts_message(date)
    if drafts_msg:
        if send_message(drafts_msg):
            print("[TELEGRAM] Drafts sent")
        else:
            success = False

    if not digest_msg and not drafts_msg:
        print("[TELEGRAM] No data to send")
        return False

    return success


def run(date: str | None = None, test: bool = False, compact: bool = False) -> bool:
    """メイン実行"""
    if test:
        return send_test()
    return notify(date, compact)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send AI news to Telegram")
    parser.add_argument("--date", default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="Send test message")
    parser.add_argument("--compact", action="store_true", help="Send compact summary only")
    args = parser.parse_args()
    result = run(args.date, args.test, args.compact)
    print(f"\n=== {'Sent!' if result else 'Not sent (check settings)'} ===")
