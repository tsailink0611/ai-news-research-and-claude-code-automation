"""
中国SNS/ニュースプラットフォーム AIトレンド取得スクリプト
主要な中国プラットフォームからAI関連のホットトピックを取得する。

対応プラットフォーム:
- 微博 (Weibo) ホットサーチ
- 知乎 (Zhihu) ホットトピック
- 36氪 (36Kr) AI関連記事
- 少数派 (SSPAI) テック記事

使い方:
    python scripts/fetch_china_news.py
"""
import json
import sys
import argparse
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, AI_KEYWORDS, ensure_dirs_for_today

# 中国AI関連キーワード（中国語 + 英語）
CN_AI_KEYWORDS = [
    "ai", "人工智能", "大模型", "llm", "gpt", "claude", "openai",
    "anthropic", "gemini", "deepseek", "通义千问", "qwen", "文心一言",
    "智谱", "百川", "kimi", "月之暗面", "机器学习", "深度学习",
    "agent", "智能体", "rag", "向量", "embedding",
]

HEADERS = {"User-Agent": "ai-news-collector/1.0"}


def fetch_weibo_hot() -> list[dict]:
    """微博ホットサーチからAI関連を取得"""
    url = "https://weibo.com/ajax/side/hotSearch"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        realtime = data.get("data", {}).get("realtime", [])

        posts = []
        for item in realtime:
            word = item.get("word", "")
            if _is_ai_related_cn(word):
                posts.append({
                    "id": f"weibo_{item.get('rank', 0)}",
                    "title": word,
                    "text": item.get("label_name", ""),
                    "score": item.get("num", 0) // 10000,
                    "likes": item.get("num", 0),
                    "url": f"https://s.weibo.com/weibo?q={word}",
                    "topic": _extract_topic_cn(word),
                    "source": "weibo",
                    "platform": "微博",
                })
        return posts
    except Exception as e:
        print(f"  [WARN] Weibo fetch failed: {e}")
        return []


def fetch_zhihu_hot() -> list[dict]:
    """知乎ホットトピックからAI関連を取得"""
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    try:
        resp = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        posts = []
        for item in data.get("data", []):
            target = item.get("target", {})
            title = target.get("title", "")
            if _is_ai_related_cn(title):
                posts.append({
                    "id": f"zhihu_{target.get('id', '')}",
                    "title": title,
                    "text": target.get("excerpt", "")[:500],
                    "score": int(item.get("detail_text", "0").replace("万热度", "0000").replace("热度", "").strip() or 0) // 10000,
                    "url": f"https://www.zhihu.com/question/{target.get('id', '')}",
                    "comments": target.get("answer_count", 0),
                    "topic": _extract_topic_cn(title),
                    "source": "zhihu",
                    "platform": "知乎",
                })
        return posts
    except Exception as e:
        print(f"  [WARN] Zhihu fetch failed: {e}")
        return []


def fetch_36kr_ai() -> list[dict]:
    """36氪からAI関連記事を取得"""
    url = "https://gateway.36kr.com/api/mis/nav/home/nav/rank/hot"
    try:
        resp = requests.post(url, json={"partner_id": "wap", "param": {"subnavType": 2}},
                             headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        posts = []
        for item in data.get("data", {}).get("hotRankList", []):
            template = item.get("templateMaterial", {})
            title = template.get("widgetTitle", "")
            if _is_ai_related_cn(title):
                posts.append({
                    "id": f"36kr_{template.get('itemId', '')}",
                    "title": title,
                    "text": template.get("summary", "")[:500],
                    "score": item.get("hot", 0) // 10000,
                    "url": f"https://36kr.com/p/{template.get('itemId', '')}",
                    "topic": _extract_topic_cn(title),
                    "source": "36kr",
                    "platform": "36氪",
                })
        return posts
    except Exception as e:
        print(f"  [WARN] 36Kr fetch failed: {e}")
        return []


def _is_ai_related_cn(text: str) -> bool:
    """AI関連かどうか判定（中国語対応）"""
    text_lower = text.lower()
    return any(kw in text_lower for kw in CN_AI_KEYWORDS)


def _extract_topic_cn(title: str) -> str:
    """中国語タイトルからトピックを推定"""
    title_lower = title.lower()
    topic_map = {
        "deepseek": "DeepSeek", "通义": "Qwen", "千问": "Qwen",
        "文心": "Ernie", "百度": "Baidu AI", "claude": "Claude",
        "gpt": "GPT", "openai": "OpenAI", "gemini": "Gemini",
        "智谱": "GLM", "kimi": "Kimi", "月之暗面": "Moonshot",
        "大模型": "LLM", "智能体": "AI Agents", "agent": "AI Agents",
        "机器人": "Robotics", "自动驾驶": "Autonomous Driving",
    }
    for keyword, topic in topic_map.items():
        if keyword in title_lower:
            return topic
    return "Chinese AI"


def _get_mock_data() -> list[dict]:
    """モックデータ（API接続不可時）"""
    now = datetime.now().isoformat()
    return [
        {"id": "cn_001", "title": "DeepSeek-V3开源：性能超越GPT-4o的国产大模型",
         "text": "DeepSeek发布V3版本，在多项基准测试中超越GPT-4o",
         "score": 850, "likes": 8500, "url": "", "created_at": now,
         "topic": "DeepSeek", "source": "china_mock", "platform": "综合"},
        {"id": "cn_002", "title": "通义千问Qwen3发布：支持200种语言",
         "text": "阿里云发布Qwen3系列模型",
         "score": 620, "likes": 6200, "url": "", "created_at": now,
         "topic": "Qwen", "source": "china_mock", "platform": "综合"},
        {"id": "cn_003", "title": "Kimi推出AI搜索功能 挑战百度搜索",
         "text": "月之暗面旗下Kimi产品新增AI搜索",
         "score": 430, "likes": 4300, "url": "", "created_at": now,
         "topic": "Kimi", "source": "china_mock", "platform": "综合"},
        {"id": "cn_004", "title": "智谱GLM-5发布 国产Agent能力大幅提升",
         "text": "智谱AI发布GLM-5，重点强化AI Agent能力",
         "score": 380, "likes": 3800, "url": "", "created_at": now,
         "topic": "GLM", "source": "china_mock", "platform": "综合"},
        {"id": "cn_005", "title": "百度文心一言4.5版本更新 支持实时联网搜索",
         "text": "百度大模型产品文心一言迎来重大更新",
         "score": 290, "likes": 2900, "url": "", "created_at": now,
         "topic": "Baidu AI", "source": "china_mock", "platform": "综合"},
    ]


def fetch_all() -> list[dict]:
    """全プラットフォームから一括取得"""
    all_posts = []

    platforms = [
        ("微博 (Weibo)", fetch_weibo_hot),
        ("知乎 (Zhihu)", fetch_zhihu_hot),
        ("36氪 (36Kr)", fetch_36kr_ai),
    ]

    for name, fetcher in platforms:
        print(f"[CHINA] Fetching {name}...")
        posts = fetcher()
        all_posts.extend(posts)
        print(f"  {name}: {len(posts)} AI posts")

    if not all_posts:
        print("[CHINA] No live data available from any platform → skipping (no mock fallback)")

    print(f"[CHINA] Total: {len(all_posts)} posts")
    return all_posts


def save_raw(posts: list[dict], date: str) -> Path:
    """rawデータを保存する"""
    filepath = RAW_DIR / date / "china_news_raw.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "fetched_at": datetime.now().isoformat(),
            "count": len(posts),
            "platforms": list(set(p.get("platform", "") for p in posts)),
            "posts": posts,
        }, f, ensure_ascii=False, indent=2)
    print(f"[CHINA] Raw data saved to {filepath}")
    return filepath


def run() -> list[dict]:
    """メイン実行"""
    date = ensure_dirs_for_today()
    posts = fetch_all()
    if posts:
        save_raw(posts, date)
    return posts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch AI news from Chinese platforms")
    args = parser.parse_args()
    results = run()
    print(f"\n=== Results: {len(results)} posts ===")
    for p in results:
        print(f"  [{p.get('platform', '')} {p.get('score', 0)}pts] {p['title'][:50]}...")
