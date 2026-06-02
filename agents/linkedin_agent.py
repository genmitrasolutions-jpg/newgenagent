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
SHARES_URL     = f"{Config.LINKEDIN_API_BASE}/shares"


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
        Publish a LinkedIn text post.
        Returns the LinkedIn post URN on success, None on failure.
        """
        if not Config.can_publish():
            logger.warning("LinkedIn credentials not configured — skipping publish")
            return None

        text = post.get("linkedin_text", "")
        if not text:
            logger.error("No linkedin_text found in post — skipping")
            return None

        payload = {
            "author": self.author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text[:3000]},  # LinkedIn 3000 char limit
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
                logger.info(f"Published: {post_id}")
                return post_id
            else:
                err = resp.json().get("message", resp.text)
                logger.error(f"LinkedIn API error [{resp.status_code}]: {err}")
                return None

        except Exception as e:
            logger.error(f"LinkedIn publish exception: {e}")
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
            post["linkedin_post_id"] = post_id
            post["status"]           = "published"
            post["published_at"]     = datetime.now().isoformat()
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
        today = datetime.now().strftime("%Y-%m-%d")
        out = Config.POSTS_DIR / f"{today}_posts.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"date": today, "run_at": datetime.now().isoformat(), "posts": posts},
                      f, indent=2, ensure_ascii=False)
