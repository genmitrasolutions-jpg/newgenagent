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
        post_type   = topic.get("post_type", "opinion")
        viral_angle = topic.get("viral_angle", topic["title"])
        hook_idea   = topic.get("hook_idea", "")
        audience    = topic.get("target_audience", "professionals")
        slot_context = POST_SLOT_CONTEXT.get(slot, "daytime")

        prompt = f"""You are a top LinkedIn creator with 500K+ followers writing a professional post for the brand '{Config.BRAND_NAME}'.

TOPIC: {topic['title']}
KEY ANGLE: {viral_angle}
HOOK IDEA: {hook_idea}
POST TYPE: {post_type}
AUDIENCE: {audience}
NICHE: {Config.CONTENT_NICHE}
POST SLOT: {slot_context} (verify the focus and style matches this slot!)
TODAY: {datetime.now().strftime('%B %d, %Y')}

ARTICLE CONTEXT:
{topic.get('summary', '')[:400]}

LINKEDIN POST RULES:
- Open with a strong PATTERN INTERRUPT hook starting with an emoji in the first 2 lines (e.g., `🚨 [Hook]`)
- Use line breaks between every 1-2 sentences for clean white space
- Keep paragraphs very short (1-2 sentences max each)
- Explain why the update matters and include one insight or takeaway
- Sound human, direct, confident — NOT corporate, avoid buzzwords like "In today's fast-paced world"
- Do NOT output lists with em-dashes. If using lists, format as emoji-prefixed or numbered lines
- End with an emoji-prefixed engagement question starting with `💡` occasionally (not in every post, but in most) to drive comments (e.g., `💡 [Engagement Question]`). If not using a question, write a strong concluding sentence.
- Keep text short and clean (150-250 words total)
- Never focus on or mention the same company more than twice per day unless it is major breaking news.
- Do NOT write footers or hashtags in the text — those will be appended programmatically

Return ONLY a valid JSON object:
{{
  "hook": "<1-2 line pattern interrupt opener starting with an emoji>",
  "body": "<full LinkedIn post body — formatted with line breaks using \n\n between paragraphs>",
  "cta": "<engaging question starting with an emoji, or empty string if not using a question>",
  "mentions": "<relevant company or creator @mentions if applicable, else empty string>",
  "hashtags": "<3-5 relevant LinkedIn hashtags space-separated>",
  "post_type": "{post_type}",
  "word_count": <approximate word count>
}}"""

        try:
            resp = self.gemini.generate_content(prompt)
            text = resp.text.strip()
            if "```" in text:
                text = re.sub(r"^```(':json)'\n'", "", text)
                text = re.sub(r"\n'```$", "", text)
            data = json.loads(text)
            return self._build_post(topic, data, slot)
        except Exception as e:
            logger.error(f"Gemini content failed: {e}")
            return self._fallback(topic, slot)

    def _build_post(self, topic: dict, data: dict, slot: int) -> dict:

        hook      = data.get("hook", "").strip()

        body      = data.get("body", "").strip()

        cta       = data.get("cta", "").strip()

        mentions  = data.get("mentions", "").strip()

        hashtags  = self._build_hashtags(topic, data.get("hashtags", ""))

        # Assemble full post text block

        full_parts = []

        if hook:

            full_parts.append(hook)

        if body:

            full_parts.append(body)

        if cta:

            full_parts.append(cta)

        full_post = "\n\n".join(full_parts).strip()

        # Assemble final LinkedIn post text

        parts = [full_post]

        if mentions:

            parts.append(f"\n{mentions}")

        parts.append(f"\n\n\n🔥 {Config.BRAND_NAME}\nFollow for daily AI & Tech updates.")

        parts.append(f"\n{hashtags}")

        final_text = "\n".join(parts).strip()

        return {

            "rank":          topic.get("rank", slot + 1),

            "slot":          slot,

            "post_time":     Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",

            "title":         topic["title"],

            "source":        topic.get("source", ""),

            "url":           topic.get("url", ""),

            "viral_angle":   topic.get("viral_angle", ""),

            "post_type":     data.get("post_type", "opinion"),

            "target_audience": topic.get("target_audience", "all"),

            "hook":          hook,

            "body":          body,

            "full_post":     full_post,

            "cta":           cta,

            "mentions":      mentions,

            "hashtags":      hashtags,

            "linkedin_text": final_text,  # Ready-to-publish text

            "word_count":    data.get("word_count", len(final_text.split())),

            "engagement_score": topic.get("linkedin_engagement_score", 5),

            "status":        "ready",

            "generated_at":  datetime.now().isoformat(),

            "scheduled_for": None,

            "published_at":  None,

            "linkedin_post_id": None,

            "analytics":     {},

        }

    # â”€â”€ Fallback (no Gemini) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _fallback(self, topic: dict, slot: int) -> dict:

        title   = topic["title"]

        source  = topic.get("source", "Tech News")

        angle   = topic.get("viral_angle", "AI is reshaping business")

        hook    = f"🚨 {title}"

        body = (

            f"Here's why this matters for the tech industry:\n\n"

            f"The pace of change in technology is moving faster than ever.\n\n"

            f"Early adopters of these updates are positioning themselves for major opportunities. "

            f"Those who wait will be left playing catch-up.\n\n"

            f"The goal is not just to keep up with these tech developments, but to actively grow with them."

        )

        cta = "💡 What do you think — is this a game-changer for the industry'"

        hashtags = self._build_hashtags(topic, "")

        full_post = f"{hook}\n\n{body}\n\n{cta}"

        final_parts = [

            full_post,

            f"\n\n\n🔥 {Config.BRAND_NAME}\nFollow for daily AI & Tech updates.",

            f"\n{hashtags}"

        ]

        final_text = "\n".join(final_parts).strip()

        return {

            "rank":          topic.get("rank", slot + 1),

            "slot":          slot,

            "post_time":     Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",

            "title":         title,

            "source":        source,

            "url":           topic.get("url", ""),

            "viral_angle":   angle,

            "post_type":     "opinion",

            "target_audience": "all",

            "hook":          hook,

            "body":          body,

            "full_post":     full_post,

            "cta":           cta,

            "mentions":      "",

            "hashtags":      hashtags,

            "linkedin_text": final_text,

            "word_count":    len(final_text.split()),

            "engagement_score": topic.get("linkedin_engagement_score", 5),

            "status":        "ready",

            "generated_at":  datetime.now().isoformat(),

            "scheduled_for": None,

            "published_at":  None,

            "linkedin_post_id": None,

            "analytics":     {},

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
