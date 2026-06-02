"""
dashboard/app.py — LinkedIn AI Automation Dashboard (Flask)
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config
from utils.logger import get_logger

logger = get_logger("dashboard")


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Config.ROOT_DIR / "templates" / "dashboard"),
        static_folder=str(Config.ROOT_DIR / "templates" / "dashboard" / "static"),
    )
    app.secret_key = Config.DASHBOARD_SECRET_KEY
    CORS(app)
    Config.ensure_dirs()

    # ── Main dashboard ─────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html",
                               brand=Config.BRAND_NAME,
                               timezone=Config.TIMEZONE,
                               post_times=Config.POST_TIMES)

    # ── Status ────────────────────────────────────────────────────────────────
    @app.route("/api/status")
    def api_status():
        return jsonify({
            "has_gemini":   Config.has_gemini(),
            "has_linkedin": Config.has_linkedin(),
            "has_twitter":  Config.has_twitter(),
            "has_reddit":   Config.has_reddit(),
            "has_newsapi":  Config.has_news_api(),
            "can_publish":  Config.can_publish(),
            "timezone":     Config.TIMEZONE,
            "brand":        Config.BRAND_NAME,
            "niche":        Config.CONTENT_NICHE,
            "post_times":   Config.POST_TIMES,
            "server_time":  datetime.now().isoformat(),
        })

    # ── Today's posts ─────────────────────────────────────────────────────────
    @app.route("/api/posts/today")
    def api_posts_today():
        return jsonify(_load_posts(datetime.now().strftime("%Y-%m-%d")))

    @app.route("/api/posts/<date>")
    def api_posts_date(date):
        return jsonify(_load_posts(date))

    # ── Post history ──────────────────────────────────────────────────────────
    @app.route("/api/posts/history")
    def api_history():
        history = []
        for i in range(14):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            d = _load_posts(date)
            if d.get("posts"):
                history.append({
                    "date": date,
                    "count": len(d["posts"]),
                    "published": sum(1 for p in d["posts"] if p.get("status") == "published"),
                    "posts": [{"title": p["title"][:60], "status": p.get("status"), "post_time": p.get("post_time")} for p in d["posts"]],
                })
        return jsonify(history)

    # ── Logs ──────────────────────────────────────────────────────────────────
    @app.route("/api/logs")
    def api_logs():
        ef = Config.LOGS_DIR / "run_events.jsonl"
        events = []
        if ef.exists():
            try:
                lines = ef.read_text(encoding="utf-8").strip().split("\n")
                for line in reversed(lines[-100:]):
                    if line.strip():
                        events.append(json.loads(line))
            except Exception:
                pass
        return jsonify(events[:60])

    # ── Analytics ─────────────────────────────────────────────────────────────
    @app.route("/api/analytics")
    def api_analytics():
        try:
            from engine.analytics import Analytics
            a = Analytics()
            # Refresh stats from LinkedIn API in real-time
            try:
                a.update_all()
            except Exception as ae:
                logger.warning(f"Real-time analytics refresh failed: {ae}")
            s = a.get_summary()
            i = a.get_optimization_insights()
            return jsonify({**s, "insights": i})
        except Exception as e:
            return jsonify({"error": str(e), "total_posts": 0})

    # ── Today's research ──────────────────────────────────────────────────────
    @app.route("/api/research/today")
    def api_research_today():
        today = datetime.now().strftime("%Y-%m-%d")
        p = Config.POSTS_DIR / f"{today}_research.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify({"topics": []})

    # ── Trigger pipeline steps ─────────────────────────────────────────────────
    @app.route("/api/run/<step>", methods=["POST"])
    def api_run(step):
        import threading

        def _run(s):
            try:
                if s == "research":
                    from agents.research_agent import ResearchAgent; ResearchAgent().run()
                elif s == "generate":
                    from agents.research_agent import ResearchAgent
                    from agents.content_agent  import ContentAgent
                    t = ResearchAgent.load_today() or ResearchAgent().run()
                    ContentAgent().run(t)
                elif s == "full":
                    from agents.research_agent import ResearchAgent
                    from agents.content_agent  import ContentAgent
                    t = ResearchAgent().run()
                    ContentAgent().run(t)
                elif s.startswith("publish"):
                    slot = int(s.replace("publish", "")) - 1
                    from agents.content_agent  import ContentAgent
                    from agents.linkedin_agent import LinkedInAgent
                    posts = ContentAgent.load_today()
                    if posts:
                        LinkedInAgent().run_slot(slot, posts)
            except Exception as e:
                logger.error(f"Manual run [{s}] failed: {e}")

        valid = ["research", "generate", "full",
                 "publish1", "publish2", "publish3", "publish4", "publish5"]
        if step not in valid:
            return jsonify({"error": f"Invalid step: {step}"}), 400

        threading.Thread(target=_run, args=(step,), daemon=True).start()
        return jsonify({"status": "started", "step": step})

    # ── Health ────────────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "time": datetime.now().isoformat()})

    import os
    if os.getenv("START_SCHEDULER", "false").lower() == "true":
        import threading
        from scheduler import start_scheduler
        logger.info("Starting background scheduler thread...")
        threading.Thread(target=start_scheduler, daemon=True).start()

    return app


def _load_posts(date: str) -> dict:
    p = Config.POSTS_DIR / f"{date}_posts.json"
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"date": date, "posts": []}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    app = create_app()
    print(f"\nDashboard: http://localhost:{Config.DASHBOARD_PORT}")
    app.run(host="0.0.0.0", port=Config.DASHBOARD_PORT, debug=False)
