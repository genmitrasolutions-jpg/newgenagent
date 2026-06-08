"""
main.py — LinkedIn AI Content Automation — Orchestrator & CLI

Usage:
  python main.py                      # Start scheduler (runs forever)
  python main.py --run-now            # Run complete pipeline immediately
  python main.py --test-research      # Test research only
  python main.py --test-generate      # Test research + content generation
  python main.py --test-publish <n>   # Test publishing slot N (1-5)
  python main.py --dashboard          # Start dashboard only
  python main.py --analytics          # Show analytics summary
  python main.py --preview            # Print all today's posts to console
"""

import sys
import io
import argparse
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("main")


def print_banner():
    print("\n" + "=" * 58)
    print("  GenMitra — AI Content Automation System")
    print("  Powered by Google Gemini + LinkedIn API")
    print("=" * 58)


def print_status():
    w = Config.validate()
    print(f"\n  Configuration:")
    print(f"    Gemini AI   : {'OK' if Config.has_gemini()   else 'Missing GEMINI_API_KEY'}")
    print(f"    LinkedIn    : {'OK' if Config.has_linkedin()  else 'Not configured (preview mode)'}")
    print(f"    Twitter/X   : {'OK' if Config.has_twitter()   else 'Disabled'}")
    print(f"    Reddit      : {'OK' if Config.has_reddit()    else 'Disabled'}")
    print(f"    NewsAPI     : {'OK' if Config.has_news_api()  else 'Disabled'}")
    print(f"    Timezone    : {Config.TIMEZONE}")
    print(f"    Brand       : {Config.BRAND_NAME}")
    print(f"    Niche       : {Config.CONTENT_NICHE}")
    print(f"    Post times  : {' | '.join(Config.POST_TIMES)}")
    if w:
        print()
        for warn in w:
            print(f"    ! {warn}")
    print()


# ── Pipeline steps ────────────────────────────────────────────────────────────

def run_full_pipeline():
    logger.info("Running complete pipeline...")
    Config.ensure_dirs()

    from agents.research_agent import ResearchAgent
    from agents.content_agent  import ContentAgent
    from agents.linkedin_agent import LinkedInAgent

    logger.info("Step 1/3 — Research")
    topics = ResearchAgent().run()

    logger.info("Step 2/3 — Generate")
    posts = ContentAgent().run(topics)

    logger.info("Step 3/3 — Preview (scheduler handles auto-publish)")
    _print_posts(posts)
    print(f"\nPipeline complete — {len(posts)} posts ready.")
    print(f"Start the scheduler to auto-publish at: {' | '.join(Config.POST_TIMES)}")


def run_test_research():
    logger.info("Testing: Research Agent")
    from agents.research_agent import ResearchAgent
    topics = ResearchAgent().run()
    print(f"\nTop {len(topics)} topics for LinkedIn:")
    for t in topics:
        print(f"  [{t.get('rank','?')}] {t['title'][:70]}")
        print(f"      Source: {t.get('source')} | LI Score: {t.get('linkedin_engagement_score',0)}/10")
        print(f"      Angle: {t.get('viral_angle','')[:80]}")
        print(f"      Hook idea: {t.get('hook_idea','')[:80]}")
        print()


def run_test_generate():
    logger.info("Testing: Research + Content Generation")
    from agents.research_agent import ResearchAgent
    from agents.content_agent  import ContentAgent

    topics = ResearchAgent.load_today() or ResearchAgent().run()
    posts  = ContentAgent().run(topics)
    _print_posts(posts)


def run_preview():
    from agents.content_agent import ContentAgent
    posts = ContentAgent.load_today()
    if not posts:
        print("No posts generated today. Run: python main.py --test-generate")
        return
    _print_posts(posts)


def run_test_publish(slot: int):
    logger.info(f"Testing: Publish slot {slot}")
    from agents.content_agent  import ContentAgent
    from agents.linkedin_agent import LinkedInAgent

    posts = ContentAgent.load_today()
    if not posts:
        print("No posts found. Run --test-generate first.")
        return

    idx = slot - 1
    agent = LinkedInAgent()
    agent.run_slot(idx, posts)
    p = posts[idx]
    print(f"\nSlot {slot}: {p.get('status')} | ID: {p.get('linkedin_post_id','N/A')}")


def run_dashboard():
    from dashboard.app import create_app
    app = create_app()
    print(f"\nDashboard: http://localhost:{Config.DASHBOARD_PORT}")
    app.run(host="0.0.0.0", port=Config.DASHBOARD_PORT, debug=False)


def run_analytics():
    from engine.analytics import Analytics
    a = Analytics()
    a.update_all()
    s = a.get_summary()
    i = a.get_optimization_insights()
    print(f"\nAnalytics Summary:")
    print(f"  Total posts    : {s['total_posts']}")
    print(f"  Total likes    : {s['total_likes']}")
    print(f"  Total comments : {s['total_comments']}")
    print(f"  Total shares   : {s['total_shares']}")
    print(f"  Avg likes      : {s['avg_likes']}")
    if isinstance(i, dict) and "recommendations" in i:
        print(f"\nRecommendations:")
        for r in i["recommendations"]:
            print(f"  - {r}")


def _print_posts(posts: list[dict]):
    for p in posts:
        print(f"\n{'='*56}")
        print(f"Post {p.get('slot',0)+1} of 5 — Scheduled: {p.get('post_time','?')}")
        print(f"Topic: {p.get('title','')[:70]}")
        print(f"Type:  {p.get('post_type','')} | Audience: {p.get('target_audience','')}")
        print(f"Score: {p.get('engagement_score',0)}/10 | Words: {p.get('word_count',0)}")
        print(f"\n--- FULL POST ---\n")
        print(p.get("linkedin_text", ""))
        print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    print_banner()
    print_status()

    parser = argparse.ArgumentParser(description="LinkedIn AI Content Automation")
    parser.add_argument("--run-now",       action="store_true")
    parser.add_argument("--test-research", action="store_true")
    parser.add_argument("--test-generate", action="store_true")
    parser.add_argument("--test-publish",  type=int, choices=[1,2,3,4,5])
    parser.add_argument("--preview",       action="store_true")
    parser.add_argument("--dashboard",     action="store_true")
    parser.add_argument("--analytics",     action="store_true")

    args = parser.parse_args()
    Config.ensure_dirs()

    if   args.run_now:         run_full_pipeline()
    elif args.test_research:   run_test_research()
    elif args.test_generate:   run_test_generate()
    elif args.test_publish:    run_test_publish(args.test_publish)
    elif args.preview:         run_preview()
    elif args.dashboard:       run_dashboard()
    elif args.analytics:       run_analytics()
    else:
        print("Starting scheduler (Ctrl+C to stop)...\n")
        from scheduler import start_scheduler
        start_scheduler()


if __name__ == "__main__":
    main()
