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
    """ダイジェスト通知メッセージを構築する"""
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
    lines.append(f"<b>AI ニュース日次レポート  {date}</b>")
    lines.append(f"<code>{len(items)} 件収集 | {len(sources)} ソース</code>")
    lines.append("")

    # 主要トピック
    lines.append("<b>今日のホットトピック</b>")
    topic_emojis = ["1.", "2.", "3.", "4.", "5.", "6."]
    for i, topic in enumerate(topics[:6]):
        count = topic.get("count", 0)
        name = _escape_html(topic.get("topic", ""))
        score = topic.get("max_score", 0)
        bar = "█" * min(int(score), 8) + "░" * (8 - min(int(score), 8))
        lines.append(f"{topic_emojis[i]} <b>{name}</b>  {count}件  <code>{bar}</code>")
    lines.append("")

    # 注目記事 TOP 5
    lines.append("<b>注目記事 TOP 5</b>")
    for i, item in enumerate(items[:5], 1):
        title = _escape_html((item.get("title") or item.get("text", ""))[:65])
        score = item.get("importance_score", 0)
        source = item.get("source", "")
        url = item.get("url", "")
        point = item.get("point") or item.get("summary_ja", "")

        lines.append(f"\n<b>{i}. {title}</b>")
        lines.append(f"   {source}  |  スコア {score:.1f}")
        if point:
            lines.append(f"   <i>{_escape_html(point[:80])}</i>")
        if url and url.startswith("http"):
            lines.append(f"   <a href=\"{url}\">記事を読む</a>")

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


def notify(date: str | None = None, compact: bool = False) -> bool:
    """パイプライン結果をTelegramに送信する"""
    if date is None:
        date = today_str()

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Skipped: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        return False

    print(f"[TELEGRAM] Sending notifications for {date}...")

    if compact:
        # コンパクト版: 1メッセージのみ
        msg = build_summary_message(date)
        if msg:
            return send_message(msg)
        print("[TELEGRAM] No data to send")
        return False

    # フル版: ダイジェスト + ドラフト候補
    success = True

    digest_msg = build_digest_message(date)
    if digest_msg:
        if send_message(digest_msg):
            print("[TELEGRAM] Digest sent")
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
