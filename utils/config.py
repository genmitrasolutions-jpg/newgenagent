"""
utils/config.py — Configuration for LinkedIn AI Content Automation System
"""

import os
from pathlib import Path
from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=True)


class Config:
    # ── Gemini AI ─────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # ── LinkedIn API ──────────────────────────────────────
    LINKEDIN_ACCESS_TOKEN: str = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_PERSON_URN: str   = os.getenv("LINKEDIN_PERSON_URN", "")
    LINKEDIN_API_BASE: str     = "https://api.linkedin.com/v2"

    # ── Optional sources ──────────────────────────────────
    X_BEARER_TOKEN: str        = os.getenv("X_BEARER_TOKEN", "")
    REDDIT_CLIENT_ID: str      = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str  = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str     = os.getenv("REDDIT_USER_AGENT", "LinkedInBot/1.0")
    NEWS_API_KEY: str          = os.getenv("NEWS_API_KEY", "")

    # ── Dashboard ─────────────────────────────────────────
    DASHBOARD_PORT: int        = int(os.getenv("DASHBOARD_PORT", "5000"))
    DASHBOARD_SECRET_KEY: str  = os.getenv("DASHBOARD_SECRET_KEY", "dev-secret")

    # ── Content settings ──────────────────────────────────
    TIMEZONE: str              = os.getenv("TIMEZONE", "Asia/Kolkata")
    BRAND_NAME: str            = os.getenv("BRAND_NAME", "GenMitra")
    CONTENT_NICHE: str         = os.getenv("CONTENT_NICHE", "Artificial Intelligence, Technology, Business, Startups")
    POSTS_PER_DAY: int         = 5

    # ── Research & generation schedule ────────────────────
    RESEARCH_TIME: str         = os.getenv("RESEARCH_TIME", "08:00")
    SELECT_TIME: str           = os.getenv("SELECT_TIME", "08:20")
    GENERATE_TIME: str         = os.getenv("GENERATE_TIME", "08:30")
    SCHEDULE_TIME: str         = os.getenv("SCHEDULE_TIME", "08:50")

    # ── 5 daily post times ────────────────────────────────
    POST_TIMES: list[str] = [
        os.getenv("POST_TIME_1", "09:00"),
        os.getenv("POST_TIME_2", "10:30"),
        os.getenv("POST_TIME_3", "12:00"),
        os.getenv("POST_TIME_4", "14:00"),
        os.getenv("POST_TIME_5", "16:00"),
    ]

    # ── Paths ─────────────────────────────────────────────
    ROOT_DIR: Path  = _ROOT
    DATA_DIR: Path  = _ROOT / "data"
    POSTS_DIR: Path = _ROOT / "data" / "posts"
    LOGS_DIR: Path  = _ROOT / "data" / "logs"

    # ── Feature flags ─────────────────────────────────────
    @classmethod
    def has_gemini(cls) -> bool:
        return bool(cls.GEMINI_API_KEY)

    @classmethod
    def has_linkedin(cls) -> bool:
        return bool(cls.LINKEDIN_ACCESS_TOKEN and cls.LINKEDIN_PERSON_URN)

    @classmethod
    def has_twitter(cls) -> bool:
        return bool(cls.X_BEARER_TOKEN)

    @classmethod
    def has_reddit(cls) -> bool:
        return bool(cls.REDDIT_CLIENT_ID and cls.REDDIT_CLIENT_SECRET)

    @classmethod
    def has_news_api(cls) -> bool:
        return bool(cls.NEWS_API_KEY)

    @classmethod
    def can_publish(cls) -> bool:
        return cls.has_linkedin()

    @classmethod
    def get_timezone(cls):
        import pytz
        return pytz.timezone(cls.TIMEZONE)

    @classmethod
    def get_now(cls):
        import pytz
        from datetime import datetime
        return datetime.now(pytz.timezone(cls.TIMEZONE))

    @classmethod
    def get_today_str(cls) -> str:
        return cls.get_now().strftime("%Y-%m-%d")

    @classmethod
    def ensure_dirs(cls):
        for d in [cls.DATA_DIR, cls.POSTS_DIR, cls.LOGS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> list[str]:
        warnings = []
        if not cls.has_gemini():
            warnings.append("GEMINI_API_KEY not set — using fallback content templates")
        if not cls.has_linkedin():
            warnings.append("LinkedIn credentials not set — running in PREVIEW mode")
        if not cls.has_twitter():
            warnings.append("X_BEARER_TOKEN not set — Twitter/X source disabled")
        if not cls.has_reddit():
            warnings.append("Reddit credentials not set — Reddit source disabled")
        if not cls.has_news_api():
            warnings.append("NEWS_API_KEY not set — NewsAPI source disabled")
        return warnings
