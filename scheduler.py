"""
scheduler.py — LinkedIn Auto-Post Scheduler
Research at 8:00 AM → Generate at 8:30 AM → Schedule at 8:50 AM
Then publishes at: 09:00 / 10:30 / 11:45 / 13:30 / 16:00
"""

import signal
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from utils.config import Config
from utils.logger import get_logger, log_run_event

logger = get_logger("scheduler")


def _parse(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


# ── Pipeline steps ────────────────────────────────────────────────────────────

def run_research():
    """8:00 AM — Discover trending topics."""
    logger.info("=" * 56)
    logger.info("STEP 1 | Research — Discovering trending topics...")
    log_run_event("STEP_START", {"step": "research", "message": "Daily research starting"})
    try:
        from agents.research_agent import ResearchAgent
        topics = ResearchAgent().run()
        logger.info(f"Research done — {len(topics)} topics selected")
    except Exception as e:
        logger.error(f"Research failed: {e}")
        log_run_event("STEP_ERROR", {"step": "research", "message": str(e)})


def run_generate():
    """8:30 AM — Generate all 5 posts."""
    logger.info("=" * 56)
    logger.info("STEP 2 | Generate — Writing LinkedIn posts...")
    log_run_event("STEP_START", {"step": "generate", "message": "Content generation starting"})
    try:
        from agents.research_agent import ResearchAgent
        from agents.content_agent  import ContentAgent

        topics = ResearchAgent.load_today()
        if not topics:
            logger.warning("No research found — running research now")
            topics = ResearchAgent().run()

        posts = ContentAgent().run(topics)
        logger.info(f"Generated {len(posts)} posts")
    except Exception as e:
        logger.error(f"Generate failed: {e}")
        log_run_event("STEP_ERROR", {"step": "generate", "message": str(e)})


def run_schedule():
    """8:50 AM — Set scheduled_for timestamps on all posts."""
    logger.info("=" * 56)
    logger.info("STEP 3 | Schedule — Setting post times...")
    log_run_event("STEP_START", {"step": "schedule", "message": "Scheduling posts"})
    try:
        import json
        from agents.content_agent import ContentAgent

        posts = ContentAgent.load_today()
        if not posts:
            logger.error("No posts to schedule")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        tz    = pytz.timezone(Config.TIMEZONE)

        for i, post in enumerate(posts):
            t = Config.POST_TIMES[i] if i < len(Config.POST_TIMES) else "09:00"
            h, m = _parse(t)
            scheduled = tz.localize(datetime.strptime(f"{today} {h:02d}:{m:02d}", "%Y-%m-%d %H:%M"))
            post["scheduled_for"] = scheduled.isoformat()
            post["post_time"]     = t
            logger.info(f"  Post {i+1} → {t}")

        Config.ensure_dirs()
        out = Config.POSTS_DIR / f"{today}_posts.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"date": today, "run_at": datetime.now().isoformat(), "posts": posts},
                      f, indent=2, ensure_ascii=False)

        log_run_event("SCHEDULE_DONE", {
            "message": f"Scheduled {len(posts)} posts",
            "times": [p.get("post_time") for p in posts],
        })
    except Exception as e:
        logger.error(f"Schedule failed: {e}")
        log_run_event("STEP_ERROR", {"step": "schedule", "message": str(e)})


def make_publish_fn(slot: int):
    """Factory: creates a publish function for a specific slot."""
    def _publish():
        t = Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "?"
        logger.info("=" * 56)
        logger.info(f"PUBLISH | Slot {slot+1} — {t}")
        log_run_event("PUBLISH_SLOT", {"message": f"Publishing slot {slot+1} at {t}", "slot": slot+1})
        try:
            from agents.content_agent  import ContentAgent
            from agents.linkedin_agent import LinkedInAgent

            posts = ContentAgent.load_today()
            if not posts:
                logger.warning("No posts found on disk — running self-healing auto-regeneration...")
                try:
                    from agents.research_agent import ResearchAgent
                    topics = ResearchAgent.load_today()
                    if not topics:
                        logger.info("No research data found — running research agent...")
                        topics = ResearchAgent().run()
                    posts = ContentAgent().run(topics)
                except Exception as ex:
                    logger.error(f"Self-healing auto-regeneration failed: {ex}")
                    return

            if not posts:
                logger.error("Failed to load or regenerate posts — aborting publish")
                return

            agent = LinkedInAgent()
            agent.run_slot(slot, posts)

            # Update analytics after a delay to let LinkedIn process the post
        except Exception as e:
            logger.error(f"Publish slot {slot+1} failed: {e}")
            log_run_event("STEP_ERROR", {"step": f"publish_{slot+1}", "message": str(e)})
    return _publish


def run_analytics_update():
    """Daily analytics refresh at 6:00 PM."""
    logger.info("Updating analytics...")
    try:
        from engine.analytics import Analytics
        a = Analytics()
        a.update_all()
        insights = a.get_optimization_insights()
        log_run_event("ANALYTICS_UPDATED", {
            "message": "Daily analytics refresh complete",
            "best_time": insights.get("best_post_time", "N/A"),
            "best_type": insights.get("best_post_type", "N/A"),
        })
    except Exception as e:
        logger.warning(f"Analytics update failed: {e}")


# ── Scheduler setup ───────────────────────────────────────────────────────────

def start_scheduler():
    tz = pytz.timezone(Config.TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)

    # Morning pipeline
    rh, rm = _parse(Config.RESEARCH_TIME)
    gh, gm = _parse(Config.GENERATE_TIME)
    sh, sm = _parse(Config.SCHEDULE_TIME)

    scheduler.add_job(run_research, CronTrigger(hour=rh, minute=rm, timezone=tz),
                      id="research", name="Research", replace_existing=True)
    scheduler.add_job(run_generate, CronTrigger(hour=gh, minute=gm, timezone=tz),
                      id="generate", name="Generate", replace_existing=True)
    scheduler.add_job(run_schedule, CronTrigger(hour=sh, minute=sm, timezone=tz),
                      id="schedule", name="Schedule", replace_existing=True)

    # 5 daily post slots
    for i, post_time in enumerate(Config.POST_TIMES):
        h, m = _parse(post_time)
        scheduler.add_job(
            make_publish_fn(i),
            CronTrigger(hour=h, minute=m, timezone=tz),
            id=f"publish_{i+1}",
            name=f"Post Slot {i+1} ({post_time})",
            replace_existing=True,
        )

    # Analytics at 6 PM
    scheduler.add_job(run_analytics_update, CronTrigger(hour=18, minute=0, timezone=tz),
                      id="analytics", name="Analytics Update", replace_existing=True)

    logger.info("=" * 56)
    logger.info("LinkedIn AI Content Automation — Scheduler Active")
    logger.info(f"  Timezone    : {Config.TIMEZONE}")
    logger.info(f"  Research    : {Config.RESEARCH_TIME}")
    logger.info(f"  Generate    : {Config.GENERATE_TIME}")
    logger.info(f"  Schedule    : {Config.SCHEDULE_TIME}")
    for i, t in enumerate(Config.POST_TIMES):
        logger.info(f"  Post {i+1}     : {t}")
    logger.info("=" * 56)

    log_run_event("SCHEDULER_START", {
        "message": "LinkedIn scheduler started",
        "timezone": Config.TIMEZONE,
        "post_times": Config.POST_TIMES,
    })

    def _shutdown(sig, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    scheduler.start()


if __name__ == "__main__":
    start_scheduler()
