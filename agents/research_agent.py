"""
agents/research_agent.py — LinkedIn Trend Discovery Engine
Scrapes RSS feeds, tech media, Reddit, Twitter/X to find viral topics.
Uses Gemini to score LinkedIn engagement potential.
"""

import feedparser
import requests
import json
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from utils.config import Config
from utils.logger import get_logger, log_run_event

logger = get_logger("research")

# ── RSS Sources (LinkedIn-relevant) ──────────────────────────────────────────
RSS_FEEDS = [
    # AI & Tech
    {"name": "OpenAI Blog",         "url": "https://openai.com/blog/rss.xml",                          "weight": 1.6},
    {"name": "Google DeepMind",     "url": "https://deepmind.google/blog/rss.xml",                     "weight": 1.5},
    {"name": "Anthropic Blog",      "url": "https://www.anthropic.com/rss.xml",                        "weight": 1.5},
    {"name": "Hugging Face Blog",   "url": "https://huggingface.co/blog/feed.xml",                     "weight": 1.4},
    {"name": "TechCrunch AI",       "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "weight": 1.3},
    {"name": "VentureBeat AI",      "url": "https://venturebeat.com/category/ai/feed/",                "weight": 1.2},
    {"name": "MIT Tech Review",     "url": "https://www.technologyreview.com/feed/",                   "weight": 1.3},
    {"name": "Wired Business",      "url": "https://www.wired.com/feed/category/business/latest/rss",  "weight": 1.1},
    # Business & Startups
    {"name": "Harvard Business Review","url": "https://feeds.hbr.org/harvardbusiness",                 "weight": 1.5},
    {"name": "Inc Magazine",        "url": "https://www.inc.com/rss",                                  "weight": 1.2},
    {"name": "Fast Company",        "url": "https://www.fastcompany.com/latest/rss",                   "weight": 1.2},
    {"name": "Y Combinator News",   "url": "https://news.ycombinator.com/rss",                        "weight": 1.3},
    {"name": "Crunchbase News",     "url": "https://news.crunchbase.com/feed/",                       "weight": 1.3},
    # Productivity & Leadership
    {"name": "First Round Review",  "url": "https://review.firstround.com/feed.xml",                  "weight": 1.4},
    {"name": "a16z Blog",           "url": "https://a16z.com/feed/",                                  "weight": 1.4},
    {"name": "The Rundown AI",      "url": "https://www.therundown.ai/rss",                           "weight": 1.3},
    {"name": "Product Hunt",        "url": "https://www.producthunt.com/feed",                        "weight": 1.2},
]

# ── Viral keyword signals for LinkedIn ────────────────────────────────────────
VIRAL_KEYWORDS = [
    "billion", "million", "funding", "raise", "launch", "announce", "new",
    "breakthrough", "first", "revolutionary", "startup", "founder", "ceo",
    "lesson", "mistake", "secret", "nobody talks", "truth", "controversial",
    "fired", "hired", "quit", "layoff", "remote", "productivity", "growth",
    "ai", "automation", "future", "prediction", "strategy", "leadership",
    "career", "salary", "negotiation", "rejected", "success", "failure",
    "tool", "framework", "how to", "why", "what happens when", "unpopular",
]

# ── LinkedIn engagement topics (always trending) ──────────────────────────────
EVERGREEN_ANGLES = [
    "AI replacing jobs vs AI creating jobs",
    "Remote work vs return to office",
    "Startup funding climate",
    "Leadership lessons from failures",
    "Career pivots and growth strategies",
    "Productivity tools and frameworks",
    "Future of work predictions",
    "Tech layoffs and their aftermath",
    "Founder stories and business lessons",
    "Side hustle to full-time business",
]


class ResearchAgent:
    """Discovers trending topics with high LinkedIn engagement potential."""

    def __init__(self):
        self.gemini = None
        if Config.has_gemini():
            try:
                import google.generativeai as genai
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.gemini = genai.GenerativeModel("gemini-3.5-flash")
                logger.info("Gemini initialized for research ✓")
            except Exception as e:
                logger.error(f"Gemini init failed: {e}")

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> list[dict]:
        log_run_event("RESEARCH_START", {"message": "LinkedIn trend discovery starting"})
        logger.info("Discovering trending topics for LinkedIn...")

        articles = self._collect_rss()

        if Config.has_twitter():
            articles += self._collect_twitter()

        if Config.has_reddit():
            articles += self._collect_reddit()

        if Config.has_news_api():
            articles += self._collect_newsapi()

        articles = self._deduplicate(articles)
        logger.info(f"Collected {len(articles)} unique articles")

        topics = self._rank(articles)
        topics = topics[:Config.POSTS_PER_DAY]

        self._save(topics)
        log_run_event("RESEARCH_DONE", {
            "message": f"Selected {len(topics)} topics",
            "topics": [t["title"][:60] for t in topics],
        })
        return topics

    # ── RSS ───────────────────────────────────────────────────────────────────

    def _collect_rss(self) -> list[dict]:
        articles = []
        cutoff = datetime.utcnow() - timedelta(hours=36)

        for feed in RSS_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                for entry in parsed.entries[:15]:
                    pub = None
                    for attr in ("published_parsed", "updated_parsed"):
                        if hasattr(entry, attr) and getattr(entry, attr):
                            try:
                                pub = datetime(*getattr(entry, attr)[:6])
                            except Exception:
                                pass
                            break

                    if pub and pub < cutoff:
                        continue

                    summary = ""
                    for attr in ("summary", "description", "content"):
                        val = getattr(entry, attr, None)
                        if val:
                            if isinstance(val, list):
                                val = val[0].get("value", "")
                            summary = BeautifulSoup(str(val), "html.parser").get_text()[:600]
                            break

                    articles.append({
                        "title":    getattr(entry, "title", "")[:200],
                        "url":      getattr(entry, "link", ""),
                        "summary":  summary,
                        "source":   feed["name"],
                        "weight":   feed["weight"],
                        "pub_date": pub.isoformat() if pub else None,
                    })
                time.sleep(0.2)
            except Exception as e:
                logger.debug(f"RSS failed [{feed['name']}]: {e}")

        logger.info(f"RSS: {len(articles)} articles from {len(RSS_FEEDS)} feeds")
        return articles

    # ── Twitter/X ─────────────────────────────────────────────────────────────

    def _collect_twitter(self) -> list[dict]:
        articles = []
        try:
            headers = {"Authorization": f"Bearer {Config.X_BEARER_TOKEN}"}
            queries = [
                "AI startup OR AI funding OR AI launch -is:retweet lang:en",
                "LinkedIn career OR leadership lesson -is:retweet lang:en",
            ]
            for q in queries:
                resp = requests.get(
                    "https://api.twitter.com/2/tweets/search/recent",
                    headers=headers,
                    params={"query": q, "max_results": 15,
                            "tweet.fields": "created_at,public_metrics"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    for tweet in resp.json().get("data", []):
                        m = tweet.get("public_metrics", {})
                        articles.append({
                            "title":   tweet["text"][:140],
                            "url":     f"https://twitter.com/i/web/status/{tweet['id']}",
                            "summary": tweet["text"],
                            "source":  "Twitter/X",
                            "weight":  1.0 + min((m.get("like_count", 0) + m.get("retweet_count", 0)) / 5000, 0.8),
                            "pub_date": tweet.get("created_at"),
                        })
        except Exception as e:
            logger.warning(f"Twitter collection failed: {e}")
        return articles

    # ── Reddit ────────────────────────────────────────────────────────────────

    def _collect_reddit(self) -> list[dict]:
        articles = []
        subs = ["Entrepreneur", "startups", "artificial", "business", "productivity",
                "ChatGPT", "MachineLearning", "tech", "career"]
        try:
            auth = requests.auth.HTTPBasicAuth(Config.REDDIT_CLIENT_ID, Config.REDDIT_CLIENT_SECRET)
            tok = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth, data={"grant_type": "client_credentials"},
                headers={"User-Agent": Config.REDDIT_USER_AGENT}, timeout=10,
            ).json().get("access_token", "")

            headers = {"Authorization": f"bearer {tok}", "User-Agent": Config.REDDIT_USER_AGENT}
            for sub in subs:
                resp = requests.get(
                    f"https://oauth.reddit.com/r/{sub}/top",
                    headers=headers, params={"limit": 8, "t": "day"}, timeout=10,
                )
                if resp.status_code == 200:
                    for post in resp.json()["data"]["children"]:
                        d = post["data"]
                        articles.append({
                            "title":   d.get("title", "")[:200],
                            "url":     f"https://reddit.com{d.get('permalink','')}",
                            "summary": d.get("selftext", "")[:500],
                            "source":  f"r/{sub}",
                            "weight":  1.0 + min(d.get("score", 0) / 8000, 0.7),
                            "pub_date": None,
                        })
        except Exception as e:
            logger.warning(f"Reddit collection failed: {e}")
        return articles

    # ── NewsAPI ───────────────────────────────────────────────────────────────

    def _collect_newsapi(self) -> list[dict]:
        articles = []
        try:
            resp = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "category": "technology",
                    "language": "en",
                    "pageSize": 20,
                    "apiKey": Config.NEWS_API_KEY,
                }, timeout=10,
            )
            if resp.status_code == 200:
                for a in resp.json().get("articles", []):
                    articles.append({
                        "title":   a.get("title", "")[:200],
                        "url":     a.get("url", ""),
                        "summary": a.get("description", "") or a.get("content", ""),
                        "source":  a.get("source", {}).get("name", "NewsAPI"),
                        "weight":  1.1,
                        "pub_date": a.get("publishedAt"),
                    })
        except Exception as e:
            logger.warning(f"NewsAPI failed: {e}")
        return articles

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        seen, unique = set(), []
        for a in articles:
            key = a["title"].lower().strip()[:70]
            if key and key not in seen:
                seen.add(key)
                unique.append(a)
        return unique

    # ── Ranking ───────────────────────────────────────────────────────────────

    def _rank(self, articles: list[dict]) -> list[dict]:
        if self.gemini and articles:
            return self._rank_gemini(articles)
        return self._rank_local(articles)

    def _rank_gemini(self, articles: list[dict]) -> list[dict]:
        logger.info("Ranking topics with Gemini for LinkedIn engagement potential...")

        items = []
        for i, a in enumerate(articles[:60]):
            items.append(f"{i+1}. [{a['source']}] {a['title']}\n   {a['summary'][:200]}")

        prompt = f"""You are a LinkedIn growth expert. Today is {datetime.now().strftime('%B %d, %Y')}.

I need to find the TOP {Config.POSTS_PER_DAY} topics from this list that will generate maximum LinkedIn engagement.

LinkedIn engagement criteria:
- Controversial or thought-provoking angle
- Relatable professional experience
- Strong opinion potential (agree/disagree)
- Save-worthy insight or framework
- Business or career relevance
- AI/tech that affects professionals
- Surprising data or counterintuitive fact
- Founder/leadership story potential

Diversity constraint:
- Never select more than 2 articles focusing on or talking about the same target company (e.g. Google, OpenAI, Apple, Microsoft) unless it is major breaking news.

Niche focus: {Config.CONTENT_NICHE}

ARTICLES:
{chr(10).join(items)}

Return ONLY a valid JSON array:
[
  {{
    "rank": 1,
    "article_index": <1-based index>,
    "title": "<title>",
    "source": "<source>",
    "linkedin_engagement_score": <1-10>,
    "viral_angle": "<the specific LinkedIn angle — e.g. contrarian take, data insight, story hook>",
    "post_type": "<story|opinion|data|howto|list|prediction>",
    "target_audience": "<founders|executives|developers|marketers|all>",
    "hook_idea": "<one punchy first-line idea for the post>"
  }}
]"""

        try:
            resp = self.gemini.generate_content(prompt)
            text = resp.text.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            ranked = json.loads(text)

            result = []
            for item in ranked:
                idx = item.get("article_index", 1) - 1
                article = articles[idx].copy() if 0 <= idx < len(articles) else {
                    "title": item["title"], "source": item["source"],
                    "url": "", "summary": "", "weight": 1.0, "pub_date": None,
                }
                article.update({
                    "rank":                     item.get("rank", 0),
                    "linkedin_engagement_score": item.get("linkedin_engagement_score", 5),
                    "viral_angle":              item.get("viral_angle", ""),
                    "post_type":                item.get("post_type", "opinion"),
                    "target_audience":          item.get("target_audience", "all"),
                    "hook_idea":                item.get("hook_idea", ""),
                })
                result.append(article)
            return result
        except Exception as e:
            logger.error(f"Gemini ranking failed: {e}")
            return self._rank_local(articles)

    def _rank_local(self, articles: list[dict]) -> list[dict]:
        logger.info("Ranking locally (keyword scoring)...")
        for a in articles:
            text = (a["title"] + " " + a.get("summary", "")).lower()
            a["_score"] = sum(1 for kw in VIRAL_KEYWORDS if kw in text) * a.get("weight", 1.0)
            a["rank"] = 0
            a["linkedin_engagement_score"] = min(int(a["_score"]), 10)
            a["viral_angle"] = "AI & business intersection"
            a["post_type"] = "opinion"
            a["target_audience"] = "all"
            a["hook_idea"] = a["title"][:80]

        articles.sort(key=lambda x: x.get("_score", 0), reverse=True)
        for i, a in enumerate(articles):
            a["rank"] = i + 1
        return articles

    # ── Persist ───────────────────────────────────────────────────────────────

    def _save(self, topics: list[dict]):
        Config.ensure_dirs()
        today = datetime.now().strftime("%Y-%m-%d")
        out = Config.POSTS_DIR / f"{today}_research.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"date": today, "run_at": datetime.now().isoformat(), "topics": topics},
                      f, indent=2, ensure_ascii=False)
        logger.info(f"Research saved -> {out}")

    @staticmethod
    def load_today() -> list[dict] | None:
        today = datetime.now().strftime("%Y-%m-%d")
        p = Config.POSTS_DIR / f"{today}_research.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f).get("topics")
        return None
