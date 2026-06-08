"""
agents/linkedin_agent.py — LinkedIn REST API Publisher
Posts text content via LinkedIn UGC Posts API.
Handles OAuth, rate limits, error recovery, and analytics fetching.
"""

import json
import time
import requests
from datetime import datetime
from utils.config import Config
from utils.logger import get_logger, log_run_event

logger = get_logger("linkedin")

UGC_POSTS_URL = f"{Config.LINKEDIN_API_BASE}/ugcPosts"
ARTICLES_URL  = f"{Config.LINKEDIN_API_BASE}/articles"


class LinkedInAgent:
    """Publishes text posts to LinkedIn via the REST API."""

    def __init__(self):
        self.token  = Config.LINKEDIN_ACCESS_TOKEN
        self.author = Config.LINKEDIN_PERSON_URN
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

    # ── Publish a single post ─────────────────────────────────────────────────

    def publish(self, post: dict) -> str | None:
        """
        Publish as a LinkedIn Article.
        Falls back to a regular UGC post if Articles API is unavailable.
        Returns the LinkedIn post URN on success, None on failure.
        """
        if not Config.can_publish():
            logger.warning("LinkedIn credentials not configured — skipping publish")
            return None

        title = post.get("article_title") or post.get("title", "")
        body  = post.get("linkedin_text", "")

        if not body:
            logger.error("No linkedin_text found in post — skipping")
            return None

        # ── Try Articles API first ────────────────────────────────────────────
        article_id = self._publish_article(title, body)
        if article_id:
            return article_id

        # ── Fallback: regular UGC text post ───────────────────────────────────
        logger.warning("Articles API failed — falling back to UGC text post")
        return self._publish_ugc_post(f"{title}\n\n{body}")

    def _publish_article(self, title: str, body: str) -> str | None:
        """Publish via LinkedIn Articles API (long-form)."""
        payload = {
            "author": self.author,
            "lifecycleState": "PUBLISHED",
            "title": {"text": title[:200]},
            "content": [
                {
                    "type": "PARAGRAPH",
                    "content": [
                        {"type": "TEXT", "text": body[:40000]}
                    ]
                }
            ]
        }
        try:
            resp = requests.post(
                ARTICLES_URL,
                headers=self._headers,
                json=payload,
                timeout=20,
            )
            if resp.status_code in (200, 201):
                post_id = resp.json().get("id", "")
                logger.info(f"Article published: {post_id}")
                return post_id
            else:
                err = resp.json().get("message", resp.text)
                logger.warning(f"Articles API [{resp.status_code}]: {err}")
                return None
        except Exception as e:
            logger.error(f"Articles API exception: {e}")
            return None

    def _publish_ugc_post(self, text: str) -> str | None:
        """Fallback: publish as a regular UGC text post."""
        payload = {
            "author": self.author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text[:3000]},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }
        try:
            resp = requests.post(
                UGC_POSTS_URL,
                headers=self._headers,
                json=payload,
                timeout=20,
            )
            if resp.status_code in (200, 201):
                post_id = resp.json().get("id", "")
                logger.info(f"UGC post published (fallback): {post_id}")
                return post_id
            else:
                err = resp.json().get("message", resp.text)
                logger.error(f"UGC API error [{resp.status_code}]: {err}")
                return None
        except Exception as e:
            logger.error(f"UGC publish exception: {e}")
            return None

    # ── Run all scheduled posts ───────────────────────────────────────────────

    def run_slot(self, slot: int, posts: list[dict]) -> list[dict]:
        """Publish the post for a specific slot index."""
        if slot >= len(posts):
            logger.warning(f"Slot {slot} out of range (only {len(posts)} posts)")
            return posts

        post = posts[slot]
        logger.info(f"Publishing slot {slot+1}/5: {post['title'][:55]}...")

        post_id = self.publish(post)

        if post_id:
            from datetime import timezone
            post["linkedin_post_id"] = post_id
            post["status"]           = "published"
            post["published_at"]     = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            log_run_event("POST_PUBLISHED", {
                "message": f"Slot {slot+1} published: {post['title'][:60]}",
                "slot": slot + 1,
                "post_time": post.get("post_time"),
                "post_id": post_id,
            })
        else:
            post["status"] = "publish_failed"
            log_run_event("POST_FAILED", {
                "message": f"Slot {slot+1} failed: {post['title'][:60]}",
                "slot": slot + 1,
            })

        self._save_posts(posts)
        return posts

    # ── Analytics ─────────────────────────────────────────────────────────────

    def fetch_post_stats(self, post_urn: str) -> dict:
        """Fetch likes, comments, shares, impressions for a post."""
        if not post_urn:
            return {}
        try:
            # Encode the URN for use as a query param
            encoded = requests.utils.quote(post_urn, safe="")
            resp = requests.get(
                f"{Config.LINKEDIN_API_BASE}/socialMetadata/{encoded}",
                headers=self._headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "likes":       data.get("totalSocialActivityCounts", {}).get("numLikes", 0),
                    "comments":    data.get("totalSocialActivityCounts", {}).get("numComments", 0),
                    "shares":      data.get("totalSocialActivityCounts", {}).get("numShares", 0),
                    "impressions": data.get("totalSocialActivityCounts", {}).get("numViews", 0),
                }
        except Exception as e:
            logger.warning(f"Stats fetch failed for {post_urn}: {e}")
        return {}

    def fetch_profile(self) -> dict:
        """Fetch basic profile info to validate credentials."""
        try:
            resp = requests.get(
                f"{Config.LINKEDIN_API_BASE}/userinfo",
                headers=self._headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"Profile fetch failed: {e}")
        return {}

    # ── Persist ───────────────────────────────────────────────────────────────

    def _save_posts(self, posts: list[dict]):
        Config.ensure_dirs()
        today = Config.get_today_str()
        out = Config.POSTS_DIR / f"{today}_posts.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"date": today, "run_at": Config.get_now().isoformat(), "posts": posts},
                       f, indent=2, ensure_ascii=False)
