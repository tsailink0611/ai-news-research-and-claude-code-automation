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
    """Step 1: データ収集"""
    print("\n" + "=" * 60)
    print("STEP 1: データ収集")
    print("=" * 60)

    from fetch_hn import run as fetch_hn
    from fetch_x_news import run as fetch_x

    hn_results = fetch_hn(limit=50)
    x_results = fetch_x(query="AI")

    print(f"\n  HN: {len(hn_results)} articles")
    print(f"  X:  {len(x_results)} posts")
    return hn_results, x_results


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


STEPS = {
    "fetch": step_fetch,
    "process": step_process,
    "digest": step_digest,
    "summarize": step_summarize,
    "drafts": step_drafts,
    "dashboard": step_dashboard,
}

ALL_STEPS = ["fetch", "process", "digest", "summarize", "drafts", "dashboard"]


def run_pipeline(steps: list[str] | None = None):
    """パイプラインを実行する"""
    if steps is None:
        steps = ALL_STEPS

    date = ensure_dirs_for_today()
    print(f"\n{'#' * 60}")
    print(f"  AI News Pipeline - {date}")
    print(f"  Steps: {', '.join(steps)}")
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
    print("\n📍 確認先:")
    print(f"  ダッシュボード: dashboard/index.html")
    print(f"  最新ダイジェスト: outputs/latest/latest_digest.md")
    print(f"  Xドラフト: outputs/latest/latest_x_drafts.md")
    print(f"  日次データ: outputs/daily/{date}/")

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
