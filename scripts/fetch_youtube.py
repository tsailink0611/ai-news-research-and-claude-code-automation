"""
YouTube AI動画リサーチスクリプト
YouTube Data API v3 で AI関連動画を検索し、字幕テキストを取得する。
APIキー未設定時はモックデータにフォールバック。

使い方:
    python scripts/fetch_youtube.py
    python scripts/fetch_youtube.py --query "Claude Code tutorial"
    python scripts/fetch_youtube.py --query "AI agents" --limit 10
"""
import json
import sys
import argparse
import subprocess
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, YOUTUBE_API_KEY, ensure_dirs_for_today

YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

DEFAULT_QUERIES = [
    "AI news this week",
    "Claude AI latest",
    "ChatGPT OpenAI news",
    "AI agents 2025",
    "LLM benchmark comparison",
    "Andrej Karpathy AI",
    "Sam Altman OpenAI",
    "Google DeepMind AI research",
    "AI coding tools cursor windsurf",
    "local LLM ollama 2025",
]

# 人気AIYouTuberチャンネルID（直接検索用）
AI_INFLUENCER_CHANNELS = {
    "Lex Fridman": "UCSHZKyawb77ixDdsGog4iWA",
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Yannic Kilcher": "UCZHmQk67mSJgfCCTn7xBfew",
    "AI Explained": "UCNJ1Ymd5yFuUPtn21xtRbbw",
    "Matt Wolfe": "UCkCJ9-4FkADOz_n_hCHbQ2A",
}


def search_videos(query: str, limit: int = 5) -> list[dict]:
    """YouTube Data API v3 で動画を検索する"""
    if not YOUTUBE_API_KEY:
        print(f"[YOUTUBE] YOUTUBE_API_KEY未設定 → スキップ（モックデータは使用しない）")
        return []

    try:
        return _search_via_api(query, limit)
    except Exception as e:
        print(f"[YOUTUBE] API error: {e} → スキップ")
        return []


def _search_via_api(query: str, limit: int) -> list[dict]:
    """YouTube Data API で検索する"""
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "maxResults": limit,
        "relevanceLanguage": "en",
        "publishedAfter": _recent_date(),
        "key": YOUTUBE_API_KEY,
    }
    resp = requests.get(YT_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
    if not video_ids:
        return []

    # 再生数等の統計情報を取得
    stats = _get_video_stats(video_ids)

    videos = []
    for item in data.get("items", []):
        vid = item["id"]["videoId"]
        snippet = item.get("snippet", {})
        stat = stats.get(vid, {})

        video = {
            "id": vid,
            "title": snippet.get("title", ""),
            "text": snippet.get("description", "")[:500],
            "url": f"https://www.youtube.com/watch?v={vid}",
            "channel": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "views": int(stat.get("viewCount", 0)),
            "likes": int(stat.get("likeCount", 0)),
            "comments": int(stat.get("commentCount", 0)),
            "score": int(stat.get("viewCount", 0)) // 1000,  # スコア互換
            "topic": _extract_topic(snippet.get("title", "")),
            "source": "youtube",
        }

        # 字幕取得を試行
        transcript = _get_transcript(vid)
        if transcript:
            video["transcript"] = transcript[:2000]

        videos.append(video)

    print(f"[YOUTUBE] API returned {len(videos)} videos for '{query}'")
    return videos


def _get_video_stats(video_ids: list[str]) -> dict:
    """動画の統計情報を取得する"""
    params = {
        "part": "statistics",
        "id": ",".join(video_ids),
        "key": YOUTUBE_API_KEY,
    }
    try:
        resp = requests.get(YT_VIDEOS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            item["id"]: item.get("statistics", {})
            for item in data.get("items", [])
        }
    except Exception:
        return {}


def _get_transcript(video_id: str) -> str | None:
    """yt-dlp で字幕テキストを取得する（インストール済みの場合）"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en",
             "--skip-download", "--print", "%(subtitles)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:2000]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _recent_date() -> str:
    """7日前のISO日付を返す"""
    from datetime import timedelta
    dt = datetime.now() - timedelta(days=2)
    return dt.strftime("%Y-%m-%dT00:00:00Z")


def _extract_topic(title: str) -> str:
    """タイトルからトピックを推定する"""
    title_lower = title.lower()
    topic_map = {
        "claude": "Claude", "anthropic": "Anthropic",
        "gpt": "GPT", "openai": "OpenAI",
        "gemini": "Gemini", "llama": "LLaMA",
        "cursor": "Cursor", "copilot": "Copilot",
        "agent": "AI Agents", "rag": "RAG",
        "fine-tun": "Fine-tuning", "benchmark": "Benchmarks",
        "tutorial": "Tutorial", "coding": "AI Coding",
    }
    for keyword, topic in topic_map.items():
        if keyword in title_lower:
            return topic
    return "AI General"


def _get_mock_data(query: str) -> list[dict]:
    """モックデータ（API未接続時）"""
    now = datetime.now().isoformat()
    return [
        {"id": "yt_001", "title": "Claude Code Complete Tutorial 2026 - Build AI Agents",
         "text": "In this video we cover everything about Claude Code...",
         "url": "https://www.youtube.com/watch?v=mock001", "channel": "AI Explorer",
         "views": 150000, "likes": 5200, "comments": 340, "score": 150,
         "published_at": now, "topic": "Claude", "source": "youtube_mock"},
        {"id": "yt_002", "title": "GPT-5 vs Claude 4: The Ultimate AI Comparison",
         "text": "Comparing the latest AI models head to head...",
         "url": "https://www.youtube.com/watch?v=mock002", "channel": "Tech Review",
         "views": 280000, "likes": 9800, "comments": 720, "score": 280,
         "published_at": now, "topic": "GPT", "source": "youtube_mock"},
        {"id": "yt_003", "title": "Build Your Own AI Agent in 30 Minutes",
         "text": "Step by step guide to building autonomous AI agents...",
         "url": "https://www.youtube.com/watch?v=mock003", "channel": "Code Academy",
         "views": 95000, "likes": 3100, "comments": 210, "score": 95,
         "published_at": now, "topic": "AI Agents", "source": "youtube_mock"},
        {"id": "yt_004", "title": "MCP Protocol Explained - Connect AI to Everything",
         "text": "Model Context Protocol is changing how we build AI tools...",
         "url": "https://www.youtube.com/watch?v=mock004", "channel": "Dev Tools",
         "views": 67000, "likes": 2400, "comments": 180, "score": 67,
         "published_at": now, "topic": "MCP", "source": "youtube_mock"},
        {"id": "yt_005", "title": "Local LLMs are Getting INSANE - Qwen, LLaMA, DeepSeek",
         "text": "The latest local language models are incredibly capable...",
         "url": "https://www.youtube.com/watch?v=mock005", "channel": "AI Underground",
         "views": 120000, "likes": 4500, "comments": 390, "score": 120,
         "published_at": now, "topic": "Local LLM", "source": "youtube_mock"},
    ]


def fetch_from_channels(limit: int = 3) -> list[dict]:
    """人気AIチャンネルから直近48時間の動画を取得する"""
    if not YOUTUBE_API_KEY:
        return []

    all_videos = []
    seen_ids = set()
    for channel_name, channel_id in AI_INFLUENCER_CHANNELS.items():
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": limit,
            "publishedAfter": _recent_date(),
            "key": YOUTUBE_API_KEY,
        }
        try:
            resp = requests.get(YT_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("items", []):
                vid = item["id"]["videoId"]
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)
                snippet = item.get("snippet", {})
                all_videos.append({
                    "id": vid,
                    "title": snippet.get("title", ""),
                    "text": snippet.get("description", "")[:500],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "channel": channel_name,
                    "published_at": snippet.get("publishedAt", ""),
                    "views": 0,
                    "likes": 0,
                    "comments": 0,
                    "score": 50,
                    "topic": _extract_topic(snippet.get("title", "")),
                    "source": "youtube_influencer",
                })
            print(f"[YOUTUBE] {channel_name}: {len(data.get('items', []))} 件")
        except Exception as e:
            print(f"[YOUTUBE] {channel_name} error: {e}")
    return all_videos


def fetch_all(queries: list[str] | None = None, limit: int = 5) -> list[dict]:
    """複数クエリで一括検索"""
    if queries is None:
        queries = DEFAULT_QUERIES

    all_videos = []
    seen_ids = set()
    for query in queries:
        print(f"[YOUTUBE] Searching: '{query}'")
        videos = search_videos(query, limit)
        for v in videos:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                all_videos.append(v)

    # 人気チャンネルから直近動画を追加
    channel_videos = fetch_from_channels(limit=3)
    for v in channel_videos:
        if v["id"] not in seen_ids:
            seen_ids.add(v["id"])
            all_videos.append(v)
    if channel_videos:
        print(f"[YOUTUBE] インフルエンサーチャンネル: +{len(channel_videos)} 件")

    print(f"[YOUTUBE] Total: {len(all_videos)} unique videos")
    return all_videos


def save_raw(videos: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "youtube_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(videos),
            "items": videos,
        }, f, ensure_ascii=False, indent=2)
    print(f"[YOUTUBE] Raw data saved to {filepath}")
    return filepath


def run(query: str | None = None, limit: int = 5) -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    if query:
        videos = fetch_all([query], limit)
    else:
        videos = fetch_all(limit=limit)
    if videos:
        save_raw(videos, date)
    return videos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI videos from YouTube")
    parser.add_argument("--query", default=None, help="Search query")
    parser.add_argument("--limit", type=int, default=5, help="Videos per query")
    args = parser.parse_args()
    results = run(args.query, args.limit)
    print(f"\n=== Results: {len(results)} videos ===")
    for v in results:
        print(f"  [{v['views']} views] {v['title'][:60]}...")
