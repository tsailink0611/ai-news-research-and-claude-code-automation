"""
共通設定モジュール
プロジェクト全体の定数・パス・設定を一元管理する
"""
import os
from pathlib import Path
from datetime import datetime

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

# データ層パス
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DAILY_DIR = OUTPUTS_DIR / "daily"
LATEST_DIR = OUTPUTS_DIR / "latest"
X_DRAFTS_DIR = OUTPUTS_DIR / "x-drafts"
DASHBOARD_DATA_DIR = DASHBOARD_DIR / "data"

# Hacker News API
HN_API_BASE = os.getenv("HN_API_BASE", "https://hacker-news.firebaseio.com/v0")
HN_TOP_STORIES_URL = f"{HN_API_BASE}/topstories.json"
HN_ITEM_URL = f"{HN_API_BASE}/item/{{item_id}}.json"

# AI関連キーワード（フィルタリング用）
AI_KEYWORDS = [
    "ai", "artificial intelligence", "llm", "gpt", "claude", "openai",
    "anthropic", "gemini", "mistral", "llama", "machine learning", "ml",
    "deep learning", "neural", "transformer", "diffusion", "stable diffusion",
    "midjourney", "copilot", "agent", "agents", "rag", "vector",
    "embedding", "fine-tuning", "mcp", "model context protocol",
    "n8n", "dify", "langchain", "llamaindex", "autogen",
    "cursor", "windsurf", "claude code", "devin",
]

# X投稿ドラフト設定
MAX_X_DRAFTS = int(os.getenv("MAX_X_DRAFTS", "30"))
X_CHAR_LIMIT = 280

# ドラフトスタイル定義
DRAFT_STYLES = {
    "breaking": {"label": "速報型", "description": "速報・最新ニュースを端的に伝える"},
    "explainer": {"label": "解説型", "description": "背景や仕組みをわかりやすく解説する"},
    "comparison": {"label": "比較型", "description": "ツールや技術を比較して示す"},
    "opinion": {"label": "意見型", "description": "考察や見解を述べる"},
    "beginner": {"label": "初心者向け整理型", "description": "初心者でもわかるように整理する"},
    "practical": {"label": "実務活用示唆型", "description": "実務でどう使えるかを示す"},
}


def today_str() -> str:
    """今日の日付文字列を返す (YYYY-MM-DD)"""
    return datetime.now().strftime("%Y-%m-%d")


def ensure_dirs_for_today():
    """今日のデータディレクトリを作成する"""
    date = today_str()
    dirs = [
        RAW_DIR / date,
        PROCESSED_DIR / date,
        DAILY_DIR / date,
        X_DRAFTS_DIR / date,
        LATEST_DIR,
        DASHBOARD_DATA_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return date
