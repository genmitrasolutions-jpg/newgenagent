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

        prompt = f"""You are an elite LinkedIn content strategist writing high-authority posts for '{Config.BRAND_NAME}'.

TOPIC: {topic['title']}
KEY ANGLE: {viral_angle}
HOOK IDEA: {hook_idea}
POST TYPE: {post_type}
AUDIENCE: {audience}
NICHE: {Config.CONTENT_NICHE}
SLOT: {slot_context}
TODAY: {datetime.now().strftime('%B %d, %Y')}

CONTEXT:
{topic.get('summary', '')[:500]}

POST STRUCTURE: Hook -> Insight -> Value -> CTA

1. HOOK (lines 1-2):
   - One bold punchy statement. No emoji.
   - Specific beats generic. Surprising beats obvious.
   - Good examples:
     "Most AI tools fail not because of tech. Because of people."
     "Nobody warns you about this side of scaling fast."
     "The best leaders I know ask more than they answer."

2. INSIGHT (3-5 short paragraphs):
   - Deliver the core idea fast and clearly
   - Use natural industry keywords (AI, automation, leadership, growth)
   - 1-2 sentences per paragraph, blank line between each
   - End with a punchy contrast pair:
     "The shift is happening.
     Most teams aren't ready."

3. VALUE (1-2 lines):
   - One clear memorable takeaway
   - Something they would screenshot

4. CTA (choose one format per post, rotate):
   - Question:    "\u{1F4AD} [Question that drives comment]"
   - Opinion ask: "\u{1F4A1} Agree or disagree - drop your view below."
   - Share ask:   "\u{1F501} Share this if your team needs to hear it."

POST RULES:
- Total length: 100-150 words (mobile-friendly)
- Short sentences, blank line between every paragraph
- Natural keyword placement, NOT stuffed
- High-authority, modern, professional tone
- Human voice - no buzzwords: no 'game-changer', 'leverage', 'utilize', 'in today's fast-paced world'
- 5-8 targeted hashtags: mix of broad (#AI #Leadership) and niche (#AIAgents #FutureOfWork)
- Do NOT write footer or hashtags in the body - appended automatically

Return ONLY valid JSON (no markdown, no extra text):
{{
  "hook": "<1-2 line scroll-stopping opener, no emoji>",
  "body": "<insight + value — \\n\\n between paragraphs — short punchy lines>",
  "cta": "<one CTA line with emoji 💭 or 💡 or 🔁>",
  "hashtags": "<5-8 targeted hashtags, mix broad+niche, no #GenMitra>",
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
            logger.error(f"Gemini content failed: {e}")
            return self._fallback(topic, slot)

    def _build_post(self, topic: dict, data: dict, slot: int) -> dict:

        hook     = data.get("hook", "").strip()
        body     = data.get("body", "").strip()
        cta      = data.get("cta", "").strip()
        hashtags = self._build_hashtags(topic, data.get("hashtags", ""))

        # Assemble post body
        full_parts = []
        if hook:
            full_parts.append(hook)
        if body:
            full_parts.append(body)
        if cta:
            full_parts.append(cta)
        full_post = "\n\n".join(full_parts).strip()

        # Assemble final text with footer
        final_text = f"{full_post}\n\n\u2014\n🔥 {Config.BRAND_NAME}\n{hashtags}"

        return {
            "rank":             topic.get("rank", slot + 1),
            "slot":             slot,
            "post_time":        Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",
            "title":            topic["title"],
            "source":           topic.get("source", ""),
            "url":              topic.get("url", ""),
            "viral_angle":      topic.get("viral_angle", ""),
            "post_type":        data.get("post_type", "opinion"),
            "target_audience":  topic.get("target_audience", "all"),
            "hook":             hook,
            "body":             body,
            "full_post":        full_post,
            "cta":              cta,
            "mentions":         "",
            "hashtags":         hashtags,
            "linkedin_text":    final_text,
            "article_title":    topic["title"],
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

        hook = "People rarely quit because of work."

        body = (
            f"{angle}\n\n"
            f"As AI and workplaces evolve faster than ever, one thing stays the same:\n\n"
            f"Those who learn and adapt early create opportunities.\n\n"
            f"Change isn't the threat.\n"
            f"Being unprepared is."
        )

        cta = "💭 What do you think is the biggest challenge this creates for professionals?"

        full_post  = f"{hook}\n\n{body}\n\n{cta}"
        final_text = f"{full_post}\n\n\u2014\n🔥 {Config.BRAND_NAME}\n{hashtags}"

        return {
            "rank":             topic.get("rank", slot + 1),
            "slot":             slot,
            "post_time":        Config.POST_TIMES[slot] if slot < len(Config.POST_TIMES) else "09:00",
            "title":            title,
            "source":           source,
            "url":              topic.get("url", ""),
            "viral_angle":      angle,
            "post_type":        "opinion",
            "target_audience":  "all",
            "hook":             hook,
            "body":             body,
            "full_post":        full_post,
            "cta":              cta,
            "mentions":         "",
            "hashtags":         hashtags,
            "linkedin_text":    final_text,
            "article_title":    title,
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

        return " ".join(all_tags[:7])

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
