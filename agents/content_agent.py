"""

agents/content_agent.py — LinkedIn Text Post Generator

Creates Hook + Story + Takeaway + CTA + Mentions + Hashtags

using Gemini. Outputs clean, human-sounding LinkedIn posts.

"""

import json

import re

from datetime import datetime

from utils.config import Config

from utils.logger import get_logger, log_run_event

logger = get_logger("content")

POST_SLOT_CONTEXT = {

    0: "9:00 AM — Trending AI News #1 (Focus: breaking AI announcements, launches, major releases from Google, OpenAI, Anthropic, NVIDIA, xAI, etc.)",

    1: "10:30 AM — AI Tool / Useful Resource (Focus: AI Tool Spotlight, SaaS releases, productivity tips, useful tech resources)",

    2: "12:00 PM — Trending Tech News #1 (Focus: breaking general technology news, acquisitions, hardware, major tech company announcements from Apple, NVIDIA, Microsoft, etc.)",

    3: "2:00 PM — Trending AI News #2 (Focus: AI research, breakthroughs, industry insights, and analysis of AI developments)",

    4: "4:00 PM — Trending Tech News #2 (Focus: breaking tech developments, launches, or Samsung/GitHub/NVIDIA updates)",

}

# â”€â”€ Trending LinkedIn hashtag bank â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

BASE_HASHTAGS = [

    "#AI", "#ArtificialIntelligence", "#Tech", "#Innovation",

    "#Startups", "#Entrepreneurship", "#Business", "#Leadership",

    "#FutureOfWork", "#Productivity", "#Growth", "#Career",

    "#Technology", "#DigitalTransformation", "#Automation",

]

TOPIC_HASHTAGS = {

    "ai":           ["#GenerativeAI", "#AITools", "#MachineLearning", "#LLM", "#AIAgents"],

    "startup":      ["#StartupLife", "#VentureCapital", "#Founders", "#BuildInPublic"],

    "leadership":   ["#LeadershipDevelopment", "#Management", "#ExecutiveCoaching"],

    "career":       ["#CareerGrowth", "#JobSearch", "#ProfessionalDevelopment", "#Hiring"],

    "productivity": ["#WorkSmarter", "#TimeManagement", "#DeepWork", "#Focus"],

    "remote":       ["#RemoteWork", "#HybridWork", "#WorkFromHome", "#DigitalNomad"],

    "funding":      ["#VentureCapital", "#AngelInvesting", "#StartupFunding", "#VC"],

    "product":      ["#ProductManagement", "#ProductLaunch", "#BuildInPublic", "#SaaS"],

    "marketing":    ["#ContentMarketing", "#GrowthHacking", "#B2BMarketing"],

    "data":         ["#DataScience", "#Analytics", "#BigData", "#DataDriven"],

}

# â”€â”€ Fallback post templates (no Gemini) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

FALLBACK_HOOKS = [

    "Most people get this completely wrong.",

    "The uncomfortable truth about {topic}:",

    "Nobody talks about this side of {topic}.",

    "3 years ago I thought {topic} was overhyped. I was wrong.",

    "This changes everything about how we think about {topic}.",

]

class ContentAgent:

    """Generates professional LinkedIn text posts for each selected topic."""

    def __init__(self):

        self.gemini = None

        if Config.has_gemini():

            try:

                import google.generativeai as genai

                genai.configure(api_key=Config.GEMINI_API_KEY)

                self.gemini = genai.GenerativeModel("gemini-3.5-flash")

                logger.info("Gemini initialized for content ✓")

            except Exception as e:

                logger.error(f"Gemini init failed: {e}")

    # â”€â”€ Public entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def run(self, topics: list[dict]) -> list[dict]:

        import time

        log_run_event("CONTENT_START", {"message": f"Generating {len(topics)} LinkedIn posts"})

        logger.info(f"Writing {len(topics)} LinkedIn posts...")

        posts = []

        for i, topic in enumerate(topics):

            logger.info("Rate limiting: sleeping 20 seconds to avoid Gemini 429 quota limits...")

            time.sleep(20)

            logger.info(f"  [{i+1}/{len(topics)}] {topic['title'][:60]}...")

            try:

                post = self._generate(topic, slot=i)

                posts.append(post)

            except Exception as e:

                logger.error(f"  Content failed for topic {i+1}: {e}")

                posts.append(self._fallback(topic, slot=i))

        self._save(posts)

        log_run_event("CONTENT_DONE", {

            "message": f"Generated {len(posts)} posts",

            "count": len(posts),

        })

        logger.info(f"Content generation complete — {len(posts)} posts ready")

        return posts

    # â”€â”€ Per-post generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _generate(self, topic: dict, slot: int) -> dict:

        return self._generate_gemini(topic, slot) if self.gemini else self._fallback(topic, slot)

    def _generate_gemini(self, topic: dict, slot: int) -> dict:
        post_type    = topic.get("post_type", "opinion")
        viral_angle  = topic.get("viral_angle", topic["title"])
        hook_idea    = topic.get("hook_idea", "")
        audience     = topic.get("target_audience", "professionals")
        slot_context = POST_SLOT_CONTEXT.get(slot, "daytime")

        prompt = f"""You are a senior LinkedIn thought-leader writing a long-form ARTICLE for the brand '{Config.BRAND_NAME}'.

TOPIC: {topic['title']}
KEY ANGLE: {viral_angle}
HOOK IDEA: {hook_idea}
POST TYPE: {post_type}
AUDIENCE: {audience}
NICHE: {Config.CONTENT_NICHE}
SLOT CONTEXT: {slot_context}
TODAY: {datetime.now().strftime('%B %d, %Y')}

ARTICLE CONTEXT:
{topic.get('summary', '')[:600]}

LINKEDIN ARTICLE RULES:
- Write a proper long-form article (600-900 words)
- Start with a punchy, bold TITLE (not clickbait — clear and insightful)
- Introduction (2-3 short paragraphs) — hook the reader with a compelling angle or statistic
- 3 clearly labeled sections with emoji-prefixed headings (e.g., `🔍 Why This Matters`)
- Each section: 3-5 short paragraphs, conversational tone, insights and examples
- Conclusion (2-3 paragraphs) — summarise the key takeaway and look ahead
- End with a strong CTA — ask a question to drive comments
- Tone: human, direct, expert — NOT corporate or buzzword-heavy
- No em-dash lists. Use numbered points or emoji-prefixed bullets if needed
- Do NOT write hashtags in the text — those will be appended separately
- Do NOT write author signature — that will be appended separately

Return ONLY a valid JSON object:
{{
  "title": "<clear, compelling article title (8-12 words)>",
  "introduction": "<2-3 paragraph intro with line breaks using \\n\\n>",
  "sections": [
    {{"heading": "<emoji + heading>", "content": "<3-5 paragraphs with \\n\\n between them>"}},
    {{"heading": "<emoji + heading>", "content": "<3-5 paragraphs>"}},
    {{"heading": "<emoji + heading>", "content": "<3-5 paragraphs>"}}
  ],
  "conclusion": "<2-3 paragraph wrap-up>",
  "cta": "<engaging question starting with 💡>",
  "hashtags": "<4-6 relevant LinkedIn hashtags space-separated>",
  "post_type": "{post_type}",
  "word_count": <approximate word count>
}}"""

        try:
            resp = self.gemini.generate_content(prompt)
            text = resp.text.strip()
            if "```" in text:
                text = re.sub(r"```json\s*", "", text)
                text = re.sub(r"```\s*$", "", text).strip()
            data = json.loads(text)
            return self._build_post(topic, data, slot)
        except Exception as e:
            logger.error(f"Gemini article generation failed: {e}")
            return self._fallback(topic, slot)

    def _build_post(self, topic: dict, data: dict, slot: int) -> dict:

        article_title = data.get("title", topic["title"]).strip()
        introduction  = data.get("introduction", "").strip()
        sections      = data.get("sections", [])
        conclusion    = data.get("conclusion", "").strip()
        cta           = data.get("cta", "").strip()
        hashtags      = self._build_hashtags(topic, data.get("hashtags", ""))

        # ── Assemble full article body ────────────────────────
        body_parts = []
        if introduction:
            body_parts.append(introduction)

        for sec in sections:
            heading = sec.get("heading", "").strip()
            content = sec.get("content", "").strip()
            if heading:
                body_parts.append(f"\n{heading}")
            if content:
                body_parts.append(content)

        if conclusion:
            body_parts.append(f"\n{conclusion}")

        if cta:
            body_parts.append(f"\n{cta}")

        full_body = "\n\n".join(body_parts).strip()

        # ── Assemble final article text ───────────────────────
        parts = [full_body]
        parts.append(f"\n\n---\n🔥 {Config.BRAND_NAME}\nFollow for daily AI & Tech insights.")
        parts.append(f"\n{hashtags}")

        final_text = "\n".join(parts).strip()

        return {
            "rank":             topic.get("rank", slot + 1),
            "slot":             slot,
            "post_time":        Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",
            "title":            article_title,
            "source":           topic.get("source", ""),
            "url":              topic.get("url", ""),
            "viral_angle":      topic.get("viral_angle", ""),
            "post_type":        data.get("post_type", "article"),
            "target_audience":  topic.get("target_audience", "all"),
            "hook":             introduction[:120] if introduction else "",
            "body":             full_body,
            "full_post":        full_body,
            "cta":              cta,
            "mentions":         "",
            "hashtags":         hashtags,
            "linkedin_text":    final_text,   # Full article body (for article API)
            "article_title":    article_title, # Separate title field for Articles API
            "word_count":       data.get("word_count", len(final_text.split())),
            "engagement_score": topic.get("linkedin_engagement_score", 5),
            "status":           "ready",
            "generated_at":     datetime.now().isoformat(),
            "scheduled_for":    None,
            "published_at":     None,
            "linkedin_post_id": None,
            "analytics":        {},
        }

    # â”€â”€ Fallback (no Gemini) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _fallback(self, topic: dict, slot: int) -> dict:
        title    = topic["title"]
        source   = topic.get("source", "Tech News")
        angle    = topic.get("viral_angle", "AI is reshaping business")
        hashtags = self._build_hashtags(topic, "")

        article_title = f"{title}"

        introduction = (
            f"The tech world never sleeps — and this week's development around {title} is proof of that.\n\n"
            f"Here's why professionals across every industry need to pay attention."
        )

        section1 = (
            f"🔍 What's Happening\n\n"
            f"{angle}\n\n"
            f"The pace of change in technology is accelerating faster than most organisations can adapt to."
        )

        section2 = (
            f"💡 Why It Matters\n\n"
            f"Early adopters of these shifts are positioning themselves for major opportunities.\n\n"
            f"Those who wait will find themselves playing an expensive game of catch-up."
        )

        section3 = (
            f"🚀 What You Should Do\n\n"
            f"The goal is not just to keep up with these tech developments — it's to actively grow with them.\n\n"
            f"Start by understanding the core change, then map it to your own work or business context."
        )

        conclusion = (
            f"Change is not the threat — being unprepared is.\n\n"
            f"The professionals and companies that thrive will be those who treat every major development "
            f"as a signal to learn, adapt, and act."
        )

        cta = "💡 What do you think — how is this going to change your industry?"

        full_body = "\n\n".join([introduction, section1, section2, section3, conclusion, cta])
        final_text = "\n".join([
            full_body,
            f"\n\n---\n🔥 {Config.BRAND_NAME}\nFollow for daily AI & Tech insights.",
            f"\n{hashtags}"
        ]).strip()

        return {
            "rank":             topic.get("rank", slot + 1),
            "slot":             slot,
            "post_time":        Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",
            "title":            article_title,
            "source":           source,
            "url":              topic.get("url", ""),
            "viral_angle":      angle,
            "post_type":        "article",
            "target_audience":  "all",
            "hook":             introduction[:120],
            "body":             full_body,
            "full_post":        full_body,
            "cta":              cta,
            "mentions":         "",
            "hashtags":         hashtags,
            "linkedin_text":    final_text,
            "article_title":    article_title,
            "word_count":       len(final_text.split()),
            "engagement_score": topic.get("linkedin_engagement_score", 5),
            "status":           "ready",
            "generated_at":     datetime.now().isoformat(),
            "scheduled_for":    None,
            "published_at":     None,
            "linkedin_post_id": None,
            "analytics":        {},
        }

    # â”€â”€ Hashtag builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_hashtags(self, topic: dict, gemini_tags: str) -> str:

        text = (topic.get("title", "") + " " + topic.get("summary", "")).lower()

        extra = []

        for keyword, tags in TOPIC_HASHTAGS.items():

            if keyword in text:

                extra.extend(tags[:2])

        gemini_list = [h.strip() for h in gemini_tags.split() if h.startswith("#")]

        brand_tag = "#" + re.sub(r"\s+", "", Config.BRAND_NAME)
        all_tags = list(dict.fromkeys([brand_tag] + gemini_list + extra + BASE_HASHTAGS))

        return " ".join(all_tags[:4])

    def _save(self, posts: list[dict]):
        Config.ensure_dirs()
        today = Config.get_today_str()
        out = Config.POSTS_DIR / f"{today}_posts.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"date": today, "run_at": Config.get_now().isoformat(), "posts": posts},
                      f, indent=2, ensure_ascii=False)
        logger.info(f"Posts saved -> {out}")

    @staticmethod
    def load_today() -> list[dict] | None:
        today = Config.get_today_str()
        p = Config.POSTS_DIR / f"{today}_posts.json"
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f).get("posts", [])
            except Exception:
                pass
        return None
