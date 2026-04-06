"""
Notionへの保存スクリプト
処理済みデータをAI技術・ナレッジDBとNFC Business Intelligence DBに保存する

Note: Notionの新しいdata_sources形式のためデータベースプロパティが使用不可。
      代わりにページブロック（rich text）でメタデータを保存する。
"""
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    from notion_client import Client
except ImportError:
    Client = None

from config import PROCESSED_DIR, today_str

# Notion設定
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_AI_DB_ID = os.getenv("NOTION_AI_DB_ID", "")
NOTION_NFC_DB_ID = os.getenv("NOTION_NFC_DB_ID", "")

# NFC系判定キーワード
NFC_KEYWORDS = [
    "nfc", "near field", "contactless", "スマートカード", "smart card", "rfid"
]

# AIカテゴリ判定マッピング
AI_CATEGORY_RULES = [
    (["n8n", "dify", "langchain", "automate"], "n8n/Automation"),
    (["agent", "agents"], "AI Agents"),
    (["mcp", "model context"], "MCP/Tools"),
    (["rag", "retrieval", "embedding", "vector"], "RAG/Knowledge"),
    (["prompt"], "Prompt Engineering"),
    (["gpt", "claude", "gemini", "llm", "model"], "LLM/Models"),
]

# タグ判定マッピング
TAG_MODEL_MAP = {
    "Claude": ["claude", "anthropic"],
    "GPT": ["gpt", "openai"],
    "Gemini": ["gemini", "google"],
    "n8n": ["n8n"],
    "Dify": ["dify"],
}

# NFC地域判定マッピング
NFC_REGION_RULES = [
    (["china", "chinese", "beijing", "shanghai", "alibaba", "tencent", "wechat"], "China"),
    (["europe", "european", "uk", "germany", "france", "eu"], "Europe"),
    (["japan", "japanese"], "Japan"),
    (["usa", "us ", "american", "silicon"], "USA"),
]

# NFCカテゴリ判定マッピング
NFC_CATEGORY_RULES = [
    (["business model", "revenue", "subscription"], "Business Model"),
    (["case study", "deploy", "implement"], "Case Study"),
    (["competitor", "competition", "rival"], "Competitor"),
    (["trend", "technology", "tech"], "Tech Trend"),
    (["smart card", "card"], "Smart Card"),
    (["iot", "physical", "digital", "phygital"], "IoT/Phygital"),
]


def is_nfc_item(item: dict) -> bool:
    text = (
        (item.get("title") or "").lower() + " " +
        (item.get("url") or "").lower()
    )
    return any(kw in text for kw in NFC_KEYWORDS)


def detect_ai_category(item: dict) -> str:
    text = (
        (item.get("title") or "").lower() + " " +
        (item.get("url") or "").lower() + " " +
        (item.get("summary") or "").lower()
    )
    for keywords, category in AI_CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "Other"


def detect_ai_tags(item: dict, score: float) -> list:
    text = (
        (item.get("title") or "").lower() + " " +
        (item.get("url") or "").lower()
    )
    tags = []
    for tag, keywords in TAG_MODEL_MAP.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    if score >= 5:
        tags.append("Must Read")
    return tags


def detect_nfc_region(item: dict) -> str:
    text = (
        (item.get("title") or "").lower() + " " +
        (item.get("url") or "").lower() + " " +
        (item.get("summary") or "").lower()
    )
    for keywords, region in NFC_REGION_RULES:
        if any(kw in text for kw in keywords):
            return region
    return "Global"


def detect_nfc_category(item: dict) -> str:
    text = (
        (item.get("title") or "").lower() + " " +
        (item.get("url") or "").lower() + " " +
        (item.get("summary") or "").lower()
    )
    for keywords, category in NFC_CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "Tech Trend"


def _make_page_title(category: str, title: str, score: float) -> str:
    """ページタイトルを生成する（カテゴリ + タイトル + スコア）"""
    clean_title = title[:120] if title else "（タイトルなし）"
    return f"[{category}] {clean_title} | score:{score:.1f}"


def title_exists_in_db(notion: "Client", db_id: str, page_title: str) -> bool:
    """同じタイトルのページがDBに既に存在するか確認する"""
    try:
        results = notion.databases.query(
            database_id=db_id,
            filter={
                "property": "Name",
                "title": {"equals": page_title}
            }
        )
        return len(results.get("results", [])) > 0
    except Exception:
        return False


def _make_blocks(meta: dict) -> list:
    """メタデータからNotionページブロックを生成する"""
    url = meta.get("url") or ""
    source = meta.get("source") or ""
    date_str = meta.get("date") or ""
    score = meta.get("score") or 0
    category = meta.get("category") or ""
    region = meta.get("region") or ""
    tags = meta.get("tags") or []
    summary = meta.get("summary") or ""

    blocks = []

    # メタデータブロック
    meta_items = []
    if category:
        meta_items.append(f"Category: {category}")
    if region:
        meta_items.append(f"Region: {region}")
    meta_items.append(f"Score: {score}")
    if source:
        meta_items.append(f"Source: {source}")
    if date_str:
        meta_items.append(f"Date: {date_str}")
    if tags:
        meta_items.append(f"Tags: {', '.join(tags)}")

    for item in meta_items:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": item}}]
            }
        })

    # URLブロック
    if url:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {"type": "text", "text": {"content": "URL: "}},
                    {"type": "text", "text": {
                        "content": url[:500],
                        "link": {"url": url[:500]}
                    }}
                ]
            }
        })

    # 要約ブロック
    if summary:
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": summary[:2000]}}]
            }
        })

    return blocks


def create_ai_page(notion: "Client", db_id: str, item: dict) -> bool:
    """AI技術・ナレッジDBにページを作成する（ブロック形式）"""
    title = item.get("title") or "（タイトルなし）"
    url = item.get("url") or ""
    source = item.get("source") or ""
    score = float(item.get("score") or 0)
    date_str = item.get("date") or item.get("published_at") or today_str()
    summary = item.get("summary") or item.get("memo") or ""

    if "T" in date_str:
        date_str = date_str[:10]

    category = detect_ai_category(item)
    tags = detect_ai_tags(item, score)

    page_title = _make_page_title(category, title, score)

    blocks = _make_blocks({
        "url": url,
        "source": source,
        "date": date_str,
        "score": score,
        "category": category,
        "tags": tags,
        "summary": summary,
    })

    notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {"title": [{"text": {"content": page_title[:2000]}}]}
        },
        children=blocks
    )
    return True


def create_nfc_page(notion: "Client", db_id: str, item: dict) -> bool:
    """NFC Business Intelligence DBにページを作成する（ブロック形式）"""
    title = item.get("title") or "（タイトルなし）"
    url = item.get("url") or ""
    source = item.get("source") or ""
    score = float(item.get("score") or 0)
    date_str = item.get("date") or item.get("published_at") or today_str()
    summary = item.get("summary") or ""

    if "T" in date_str:
        date_str = date_str[:10]

    region = detect_nfc_region(item)
    category = detect_nfc_category(item)

    page_title = _make_page_title(f"NFC/{region}", title, score)

    blocks = _make_blocks({
        "url": url,
        "source": source,
        "date": date_str,
        "score": score,
        "category": category,
        "region": region,
        "summary": summary,
    })

    notion.pages.create(
        parent={"database_id": db_id},
        properties={
            "Name": {"title": [{"text": {"content": page_title[:2000]}}]}
        },
        children=blocks
    )
    return True


def run(date: str = None, dry_run: bool = False) -> dict:
    """
    処理済みデータをNotionに保存する

    Args:
        date: 対象日付（YYYY-MM-DD）。Noneの場合は今日
        dry_run: Trueの場合は保存せず件数だけ表示

    Returns:
        {'ai_saved': N, 'nfc_saved': N, 'skipped': N}
    """
    if date is None:
        date = today_str()

    result = {"ai_saved": 0, "nfc_saved": 0, "skipped": 0}

    processed_file = PROCESSED_DIR / date / "processed_articles.json"
    if not processed_file.exists():
        print(f"[notify_notion] ファイルが見つかりません: {processed_file}")
        return result

    with open(processed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        articles = data.get("items", [])
    else:
        articles = data

    if not articles:
        print("[notify_notion] 記事データが空です")
        return result

    print(f"[notify_notion] {len(articles)} 件を処理対象として読み込みました")

    if dry_run:
        ai_count = sum(1 for a in articles if not is_nfc_item(a))
        nfc_count = sum(1 for a in articles if is_nfc_item(a))
        print(f"[dry-run] AI系: {ai_count} 件 / NFC系: {nfc_count} 件")
        result["ai_saved"] = ai_count
        result["nfc_saved"] = nfc_count
        return result

    if Client is None:
        print("[notify_notion] notion-client がインストールされていません")
        return result

    if not NOTION_API_KEY:
        print("[notify_notion] NOTION_API_KEY が設定されていません")
        return result

    notion = Client(auth=NOTION_API_KEY)

    for article in articles:
        if is_nfc_item(article):
            if not NOTION_NFC_DB_ID:
                result["skipped"] += 1
                continue
            # タイトルベースの重複チェック
            title = article.get("title") or ""
            score = float(article.get("score") or 0)
            region = detect_nfc_region(article)
            page_title = _make_page_title(f"NFC/{region}", title, score)
            if title_exists_in_db(notion, NOTION_NFC_DB_ID, page_title):
                print(f"[skip] NFC重複: {title[:60]}")
                result["skipped"] += 1
                continue
            try:
                create_nfc_page(notion, NOTION_NFC_DB_ID, article)
                print(f"[NFC] 保存: {title[:60]}")
                result["nfc_saved"] += 1
            except Exception as e:
                print(f"[error] NFC保存失敗: {e} | {title[:60]}")
                result["skipped"] += 1
        else:
            if not NOTION_AI_DB_ID:
                result["skipped"] += 1
                continue
            title = article.get("title") or ""
            score = float(article.get("score") or 0)
            category = detect_ai_category(article)
            page_title = _make_page_title(category, title, score)
            if title_exists_in_db(notion, NOTION_AI_DB_ID, page_title):
                print(f"[skip] AI重複: {title[:60]}")
                result["skipped"] += 1
                continue
            try:
                create_ai_page(notion, NOTION_AI_DB_ID, article)
                print(f"[AI] 保存: {title[:60]}")
                result["ai_saved"] += 1
            except Exception as e:
                print(f"[error] AI保存失敗: {e} | {title[:60]}")
                result["skipped"] += 1

    print(
        f"[notify_notion] 完了 — AI: {result['ai_saved']} 件, "
        f"NFC: {result['nfc_saved']} 件, スキップ: {result['skipped']} 件"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="処理済みデータをNotionに保存する")
    parser.add_argument("--date", type=str, default=None, help="対象日付 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="保存せず件数だけ表示する")
    args = parser.parse_args()

    run(date=args.date, dry_run=args.dry_run)
