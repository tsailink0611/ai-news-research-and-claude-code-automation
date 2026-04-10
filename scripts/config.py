"""
共通設定モジュール
プロジェクト全体の定数・パス・設定を一元管理する
"""
import os
from pathlib import Path
from datetime import datetime

# .env ファイルを読み込む
PROJECT_ROOT = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass  # python-dotenv 未インストール時はシステム環境変数のみ使用
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
    "nfc", "near field communication", "contactless", "smart card", "nfc card",
    "nfc tag", "nfc inlay", "rfid", "phygital", "physical digital",
    "tap to pay", "tap and go", "digital business card", "nfc business",
    "近场通信", "非接触", "スマートカード",
]

# NFCキーワード（NFC事業モニタリング専用）
NFC_KEYWORDS = [
    "nfc", "near field communication", "contactless card", "smart card",
    "nfc card", "nfc tag", "nfc inlay", "rfid nfc", "phygital",
    "tap to pay", "tap and go", "digital business card", "nfc business",
    "nfc marketing", "nfc solution", "nfc retail", "nfc hospitality",
    "nfc loyalty", "nfc payment", "nfc access", "nfc authentication",
    "近场通信", "nfc卡", "智能卡", "非接触式", "nfc标签",
]

# NFC専用SerpApi検索クエリ
NFC_SEARCH_QUERIES = [
    "NFC business card solution USA 2025",
    "NFC smart card marketing Europe 2025",
    "NFC contactless business China 2025",
    "NFC phygital retail case study",
    "digital NFC card startup funding",
    "NFC loyalty program business model",
]

# Grok API (X AI)
GROK_API_KEY = os.getenv("GROK_API_KEY", "")
GROK_API_BASE = os.getenv("GROK_API_BASE", "https://api.x.ai/v1")

# Anthropic Claude API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# YouTube Data API v3
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Reddit (公開JSON APIはキー不要、OAuth使用時のみ必要)
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_SUBREDDITS = [
    "ClaudeAI", "ChatGPT", "LocalLLaMA", "MachineLearning",
    "artificial", "singularity",
]

# Google Trends (pytrends、APIキー不要)

# Product Hunt API
PRODUCTHUNT_ACCESS_TOKEN = os.getenv("PRODUCTHUNT_ACCESS_TOKEN", "")

# SerpApi
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

# X API (ブックマーク取得用)
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")

# Supabase（canonical store）
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Telegram Bot（プッシュ通知用）
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# X投稿ドラフト設定
MAX_X_DRAFTS = int(os.getenv("MAX_X_DRAFTS", "10"))
X_CHAR_LIMIT = 280

# ─── 二層レーン定義 ──────────────────────────────────────────────
# Frontier Radar: 先端探索・R&D・未来の商材候補
FRONTIER_SOURCES = {
    "TechCrunch AI", "VentureBeat AI", "The Verge AI", "Ars Technica Tech",
    "MIT Tech Review AI", "Simon Willison", "Latent Space", "Import AI",
    "TheSequence", "HuggingFace Blog", "GitHub Trending",
    "HackerNews", "Reddit", "Product Hunt", "China SNS",
}

# Proposal Radar: 今すぐ提案に使える国内事例・ツール・業種情報
PROPOSAL_SOURCES = {
    "ITmedia AI+", "AINOW", "日経クロステック",
    "Zenn AI", "Qiita AI",
    "Google Trends", "SerpApi", "X Bookmarks",
}

# Frontier Score 計算用キーワード
FRONTIER_KEYWORDS = [
    "llm", "agent", "mcp", "rag", "embedding", "transformer", "fine-tun",
    "benchmark", "architecture", "open source", "release", "github", "model",
    "arxiv", "research", "multimodal", "reasoning", "autonomous", "agentic",
    "中国", "china", "alibaba", "tencent", "baidu", "wechat",
    "plugin", "extension", "workflow", "automation tool",
]

# Proposal Score 計算用キーワード
PROPOSAL_INDUSTRY_KEYWORDS = [
    "不動産", "建設", "製造", "士業", "中小企業", "smb", "工務店",
    "ショールーム", "内覧", "施工", "受発注", "現場",
]
PROPOSAL_TOOL_KEYWORDS = [
    "n8n", "dify", "chatbot", "チャットボット", "自動化", "ノーコード",
    "ローコード", "rpa", "業務効率", "業務自動化", "工数削減", "コスト削減",
    "導入事例", "活用事例", "成功事例",
]
PROPOSAL_SUBSIDY_KEYWORDS = [
    "補助金", "助成金", "it導入", "ものづくり補助", "公募", "申請", "交付",
]

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
