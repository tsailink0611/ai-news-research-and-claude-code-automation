"""
パイプライン実行スクリプト
収集→処理→ダイジェスト→X要約→ドラフト生成→ダッシュボード更新 を一括実行する

使い方:
    python scripts/run_pipeline.py              # 全ステップ実行
    python scripts/run_pipeline.py --step fetch  # 個別ステップ
    python scripts/run_pipeline.py --step digest
    python scripts/run_pipeline.py --step drafts
"""
import sys
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import ensure_dirs_for_today


def step_fetch():
    """Step 1: データ収集（全10ソース）"""
    print("\n" + "=" * 60)
    print("STEP 1: データ収集（10ソース）")
    print("=" * 60)

    results = {}

    # 1. Grok API × X検索（速報系の最速手段）
    from fetch_x_news import run as fetch_x
    x_results = fetch_x(query="AI")
    results["x_grok"] = len(x_results)
    print(f"  [1/10] Grok×X検索: {len(x_results)} posts")

    # 2. YouTube字幕取得（海外AI動画リサーチ）
    from fetch_youtube import run as fetch_yt
    yt_results = fetch_yt()
    results["youtube"] = len(yt_results)
    print(f"  [2/10] YouTube: {len(yt_results)} videos")

    # 3. HackerNews（エンジニア・開発者トレンド）
    from fetch_hn import run as fetch_hn
    hn_results = fetch_hn(limit=50)
    results["hackernews"] = len(hn_results)
    print(f"  [3/10] HackerNews: {len(hn_results)} articles")

    # 4. Reddit分析（海外ユーザーのリアルな声）
    from fetch_reddit import run as fetch_reddit
    reddit_results = fetch_reddit()
    results["reddit"] = len(reddit_results)
    print(f"  [4/10] Reddit: {len(reddit_results)} posts")

    # 5. 中国SNSトレンド
    from fetch_china_news import run as fetch_china
    china_results = fetch_china()
    results["china"] = len(china_results)
    print(f"  [5/10] 中国SNS: {len(china_results)} posts")

    # 6. Google Trends（検索ボリュームのトレンド）
    from fetch_google_trends import run as fetch_trends
    trends_results = fetch_trends()
    results["google_trends"] = len(trends_results)
    print(f"  [6/10] Google Trends: {len(trends_results)} items")

    # 7. Product Hunt（新サービスの発見）
    from fetch_producthunt import run as fetch_ph
    ph_results = fetch_ph()
    results["producthunt"] = len(ph_results)
    print(f"  [7/10] Product Hunt: {len(ph_results)} products")

    # 8. SerpApi × Google検索分析
    from fetch_serpapi import run as fetch_serp
    serp_results = fetch_serp()
    results["serpapi"] = len(serp_results)
    print(f"  [8/10] SerpApi: {len(serp_results)} items")

    # 9. Xブックマーク
    from fetch_x_bookmarks import run as fetch_bm
    bm_results = fetch_bm()
    results["x_bookmarks"] = len(bm_results)
    print(f"  [9/10] Xブックマーク: {len(bm_results)} posts")

    # 10. (将来) Claude Codeログ検索はローカル専用のため除外

    total = sum(results.values())
    print(f"\n  合計: {total} items from {len(results)} sources")
    return results


def step_process():
    """Step 2: データ処理"""
    print("\n" + "=" * 60)
    print("STEP 2: データ処理")
    print("=" * 60)

    from process_data import process
    result = process()
    print(f"\n  Processed: {result['stats'].get('total_items', 0)} items")
    return result


def step_digest():
    """Step 3: ダイジェスト生成"""
    print("\n" + "=" * 60)
    print("STEP 3: ダイジェスト生成")
    print("=" * 60)

    from generate_digest import run as gen_digest
    md = gen_digest()
    if md:
        print(f"\n  Digest generated ({len(md)} chars)")
    return md


def step_summarize():
    """Step 4: X向け要約"""
    print("\n" + "=" * 60)
    print("STEP 4: X向け再要約")
    print("=" * 60)

    from summarize_for_x import run as summarize
    summaries = summarize()
    print(f"\n  Summaries: {len(summaries)}")
    return summaries


def step_drafts():
    """Step 5: Xドラフト生成"""
    print("\n" + "=" * 60)
    print("STEP 5: Xドラフト量産")
    print("=" * 60)

    from generate_x_drafts import run as gen_drafts
    drafts = gen_drafts()
    print(f"\n  Drafts: {len(drafts)}")
    return drafts


def step_dashboard():
    """Step 6: ダッシュボード更新"""
    print("\n" + "=" * 60)
    print("STEP 6: ダッシュボード更新")
    print("=" * 60)

    from build_dashboard_data import run as build_dash
    data = build_dash()
    print(f"\n  Dashboard updated")
    return data


def step_enrich():
    """Step 6.5: 日本語要約生成"""
    print("\n" + "=" * 60)
    print("STEP 6.5: 日本語要約生成（Claude Haiku）")
    print("=" * 60)

    from enrich_summaries import run as enrich
    result = enrich()
    print(f"\n  Enriched: {result['enriched']} 件")
    return result


def step_notion():
    """Step 7: Notion保存"""
    print("\n" + "=" * 60)
    print("STEP 7: Notion保存（AI・NFC分類）")
    print("=" * 60)

    from notify_notion import run as save_notion
    result = save_notion()
    print(f"\n  Notion: AI={result['ai_saved']} NFC={result['nfc_saved']} skip={result['skipped']}")
    return result


def step_notify():
    """Step 8: Telegram通知"""
    print("\n" + "=" * 60)
    print("STEP 8: Telegram通知")
    print("=" * 60)

    from notify_telegram import notify
    success = notify()
    if success:
        print(f"\n  Telegram notification sent!")
    else:
        print(f"\n  Telegram skipped (not configured or no data)")
    return success


STEPS = {
    "fetch": step_fetch,
    "process": step_process,
    "digest": step_digest,
    "summarize": step_summarize,
    "drafts": step_drafts,
    "dashboard": step_dashboard,
    "enrich": step_enrich,
    "notion": step_notion,
    "notify": step_notify,
}

ALL_STEPS = ["fetch", "process", "digest", "summarize", "drafts", "dashboard", "enrich", "notion", "notify"]


def run_pipeline(steps: list[str] | None = None):
    """パイプラインを実行する"""
    if steps is None:
        steps = ALL_STEPS

    date = ensure_dirs_for_today()
    print(f"\n{'#' * 60}")
    print(f"  AI News Pipeline - {date}")
    print(f"  Steps: {', '.join(steps)}")
    print(f"  Sources: Grok/X, YouTube, HN, Reddit, China SNS,")
    print(f"           Google Trends, Product Hunt, SerpApi, X Bookmarks")
    print(f"{'#' * 60}")

    start = time.time()
    results = {}

    for step_name in steps:
        if step_name in STEPS:
            try:
                results[step_name] = STEPS[step_name]()
            except Exception as e:
                print(f"\n  [ERROR] Step '{step_name}' failed: {e}")
                results[step_name] = None
        else:
            print(f"\n  [WARN] Unknown step: {step_name}")

    elapsed = time.time() - start
    print(f"\n{'#' * 60}")
    print(f"  Pipeline completed in {elapsed:.1f}s")
    print(f"{'#' * 60}")

    # 確認先を表示
    print("\n  確認先:")
    print(f"  ダッシュボード: dashboard/index.html")
    print(f"  最新ダイジェスト: outputs/latest/latest_digest.md")
    print(f"  Xドラフト: outputs/latest/latest_x_drafts.md")
    print(f"  日次データ: outputs/daily/{date}/")
    print(f"  Notion: https://notion.so")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AI news pipeline")
    parser.add_argument("--step", choices=list(STEPS.keys()), help="Run specific step only")
    parser.add_argument("--steps", nargs="+", choices=list(STEPS.keys()), help="Run specific steps")
    args = parser.parse_args()

    if args.step:
        run_pipeline([args.step])
    elif args.steps:
        run_pipeline(args.steps)
    else:
        run_pipeline()
