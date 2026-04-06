"""
GitHub Trendingスクリプト
今日のトレンドAIリポジトリを取得する（スター数上位 / AI関連のみ）

取得対象:
  - python/javascript/any言語のAI系トレンドリポジトリ
  - LLM・エージェント・ツール・プラグイン系
  - Claude Code / n8n / Dify / RAG / MCP 関連
"""
import json
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from config import RAW_DIR, ensure_dirs_for_today

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)"}

# AI関連リポジトリ判定キーワード
AI_REPO_KEYWORDS = [
    "llm", "gpt", "claude", "gemini", "openai", "anthropic",
    "ai", "agent", "rag", "embedding", "vector", "langchain",
    "n8n", "dify", "mcp", "model", "prompt", "chat", "copilot",
    "transformer", "diffusion", "stable", "hugging", "ollama",
    "tool", "plugin", "extension", "automation", "workflow",
    "vscode", "cursor", "cline", "continue", "replit",
    "code generation", "code assist",
]

# 取得するURL一覧（言語フィルターなし + Python + JavaScript）
TRENDING_URLS = [
    ("All Languages", "https://github.com/trending?since=daily"),
    ("Python", "https://github.com/trending/python?since=daily"),
    ("JavaScript", "https://github.com/trending/javascript?since=daily"),
    ("TypeScript", "https://github.com/trending/typescript?since=daily"),
]

MAX_PER_URL = 15   # 各URLから最大スクレイプ数
TOTAL_LIMIT = 20   # AI関連のみ絞った後の最大件数
MIN_STARS_TODAY = 5  # 今日のスター5以上のみ（0は除外）


def _is_ai_repo(name: str, description: str) -> bool:
    """リポジトリがAI関連かどうか判定する"""
    text = (name + " " + description).lower()
    return any(kw in text for kw in AI_REPO_KEYWORDS)


def _extract_star_count(text: str) -> int:
    """「1,234 stars today」などからスター数を抽出する"""
    text = text.replace(",", "").replace(" ", "")
    import re
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 0


def scrape_trending_page(label: str, url: str) -> list[dict]:
    """GitHubトレンドページをスクレイピングする"""
    print(f"  [{label}] 取得中: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        repo_items = soup.select("article.Box-row")

        if not repo_items:
            print(f"  [{label}] リポジトリが見つかりません")
            return []

        results = []
        for item in repo_items[:MAX_PER_URL]:
            # リポジトリ名
            name_el = item.select_one("h2 a")
            if not name_el:
                continue
            repo_path = name_el.get("href", "").strip("/")  # "owner/repo"
            repo_name = repo_path.replace("/", " / ")

            # 説明
            desc_el = item.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            # AI関連でなければスキップ
            if not _is_ai_repo(repo_path, description):
                continue

            # スター数が少ないものはスキップ（後で集計するので仮の判定）
            # ※ stars_todayは後から抽出するため、ここでは通過させておく

            # スター数（今日）
            star_today_el = item.select_one("[aria-label*='star today'], .float-sm-right")
            star_today_text = star_today_el.get_text(strip=True) if star_today_el else ""
            stars_today = _extract_star_count(star_today_text)

            # 総スター数
            total_star_el = item.select_one("a[href*='stargazers']")
            total_stars_text = total_star_el.get_text(strip=True) if total_star_el else ""
            total_stars = _extract_star_count(total_stars_text)

            # 言語
            lang_el = item.select_one("[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else ""

            repo_url = f"https://github.com/{repo_path}"
            repo_id = hashlib.md5(repo_url.encode()).hexdigest()[:12]

            # 重要度スコア（今日スター数ベース）
            score = round(min(stars_today / 50, 5.0) + min(total_stars / 5000, 3.0), 2)

            results.append({
                "id": repo_id,
                "title": f"[GitHub] {repo_name}",
                "url": repo_url,
                "source": "GitHub Trending",
                "source_type": "github_trending",
                "topic": "AI Tools & Repos",
                "summary": description[:300],
                "language": language,
                "stars_today": stars_today,
                "total_stars": total_stars,
                "trending_label": label,
                "published_at": datetime.now(timezone.utc).date().isoformat(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "score": score,
                "importance_score": score,
            })

        print(f"  [{label}] AI関連 {len(results)} 件取得")
        return results

    except Exception as e:
        print(f"  [{label}] エラー: {e}")
        return []


def run() -> list[dict]:
    """
    GitHub TrendingからAI関連リポジトリを取得する

    Returns:
        リポジトリリスト
    """
    date = ensure_dirs_for_today()
    out_path = RAW_DIR / date / "github_trending.json"

    print(f"[fetch_github_trending] {len(TRENDING_URLS)} ページから取得開始")
    all_repos = []
    seen_urls = set()

    for label, url in TRENDING_URLS:
        repos = scrape_trending_page(label, url)
        for repo in repos:
            if repo["url"] not in seen_urls:
                seen_urls.add(repo["url"])
                all_repos.append(repo)
        time.sleep(1.0)  # GitHub への負荷軽減

    # 今日のスター数が最低基準を満たすものだけ残す
    all_repos = [r for r in all_repos if r.get("stars_today", 0) >= MIN_STARS_TODAY]

    # スター数（今日）でソートして上位のみ
    all_repos.sort(key=lambda x: x.get("stars_today", 0), reverse=True)
    all_repos = all_repos[:TOTAL_LIMIT]

    print(f"\n[fetch_github_trending] AI関連リポジトリ: {len(all_repos)} 件")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_repos, f, ensure_ascii=False, indent=2)
    print(f"[fetch_github_trending] 保存: {out_path}")

    return all_repos


if __name__ == "__main__":
    results = run()
    print(f"\n取得完了: {len(results)} 件")
    for r in results[:10]:
        print(f"  ⭐{r.get('stars_today', 0):>4} 今日 | {r['title'][:55]} | {r.get('language','')}")
