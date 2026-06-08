# 🤖 GenMitra — AI Content Automation System

> **Fully autonomous AI system** that researches top AI news daily, generates premium Instagram carousel posts, and publishes them automatically at 9:00 AM — zero manual effort required.

---

## ✨ What It Does

| Time | Action |
|------|--------|
| **8:00 AM** | 🔍 Researches 15+ AI news sources (RSS, blogs, optional Twitter/X & Reddit) |
| **8:15 AM** | ✍️ Generates slide copy, captions & hashtags via Google Gemini |
| **8:45 AM** | 🎨 Renders 25 premium 1080×1080px carousel slides (5 posts × 5 slides) |
| **9:00 AM** | 📸 Publishes all 5 carousel posts to Instagram automatically |

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Credentials

```bash
copy .env.example .env
```

Edit `.env` and fill in your credentials:

| Variable | How to Get |
|----------|-----------|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `INSTAGRAM_ACCESS_TOKEN` | Meta Developer Portal → Long-lived token |
| `INSTAGRAM_USER_ID` | Meta Graph API Explorer → `/me?fields=id` |
| `CLOUDINARY_CLOUD_NAME` etc. | [cloudinary.com](https://cloudinary.com) → Dashboard → Settings |

> **Note:** The system works in **preview mode** without Instagram/Cloudinary — it will research, generate, and render slides, but skip publishing.

### 3. Test Each Step

```bash
# Test research only
python main.py --test-research

# Test content generation
python main.py --test-generate

# Test image rendering (generates PNG files)
python main.py --test-render

# Test full pipeline without publishing
python main.py --test-upload

# Run the complete pipeline right now
python main.py --run-now
```

### 4. Start the Dashboard

```bash
python dashboard/app.py
# Open http://localhost:5000
```

### 5. Start the Automated Scheduler

```bash
python main.py
```

This starts the scheduler and runs forever. It will execute the pipeline daily at the configured times.

---

## 🌐 Dashboard

Open `http://localhost:5000` to see:

- **Command Center** — Pipeline status, countdown to next publish, live stats
- **Today's Posts** — Generated carousel previews with captions
- **Analytics** — Likes, reach, saves, comments from Instagram
- **Activity Logs** — Full event history

You can also **manually trigger any step** from the dashboard sidebar.

---

## 🔧 Running as a Background Service (Windows)

To run the scheduler 24/7 in the background:

```bash
# Option 1: Windows Task Scheduler
# Create a task that runs: python "e:\insta agents\main.py" at system startup

# Option 2: Run in background with pythonw
start /B pythonw "e:\insta agents\main.py"

# Option 3: Run dashboard and scheduler together
python dashboard/app.py &
python main.py
```

---

## 📁 Project Structure

```
e:/insta agents/
├── .env                    # Your credentials (never share this!)
├── .env.example            # Template for credentials
├── requirements.txt        # Python dependencies
├── main.py                 # Entry point + CLI
├── scheduler.py            # APScheduler cron jobs
│
├── agents/
│   ├── research_agent.py   # AI news research & ranking
│   ├── content_agent.py    # Caption & slide copy generation
│   └── instagram_agent.py  # Instagram Graph API publisher
│
├── engine/
│   ├── image_renderer.py   # HTML → PNG via Playwright
│   ├── cloudinary_uploader.py # Image hosting
│   └── analytics.py        # Post metrics fetcher
│
├── templates/
│   ├── slide_templates/    # 5 premium HTML slide designs
│   └── dashboard/          # Flask dashboard UI
│
├── dashboard/
│   └── app.py              # Flask web server
│
└── data/
    ├── posts/              # Daily generated post JSON
    ├── images/             # Rendered carousel PNGs
    └── logs/               # Automation logs
```

---

## 🔑 Instagram Setup Guide

1. **Convert to Business/Creator account** in Instagram settings
2. **Create a Meta Developer App** at [developers.facebook.com](https://developers.facebook.com)
3. **Add Instagram product** to your app
4. **Connect your Instagram account** to a Facebook Page
5. **Get long-lived access token** (valid 60 days, auto-refreshable):
   ```
   GET https://graph.facebook.com/v22.0/oauth/access_token?
       grant_type=fb_exchange_token&
       client_id={app-id}&
       client_secret={app-secret}&
       fb_exchange_token={short-lived-token}
   ```
6. **Get your Instagram User ID**:
   ```
   GET https://graph.facebook.com/v22.0/me?fields=id,name&access_token={token}
   ```

---

## ⚙️ Configuration

Edit `.env` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `TIMEZONE` | `Asia/Kolkata` | Your timezone for scheduling |
| `PUBLISH_TIME` | `09:00` | Daily publish time (24h) |
| `POSTS_PER_DAY` | `5` | Number of posts to publish daily |
| `BRAND_NAME` | `GenMitra` | Brand name shown on slides |

---

## 📊 Analytics

After posts are published, analytics are automatically fetched from Instagram:
- **Reach** — How many accounts saw the post
- **Likes** — Total likes
- **Saves** — High-intent saves (great engagement signal)
- **Comments** — Comments count
- **Shares** — Times shared

Analytics data is stored in `data/analytics.json` and displayed on the dashboard.

---

## 🆘 Troubleshooting

**`playwright install chromium` fails:**
```bash
pip install playwright
playwright install chromium --with-deps
```

**Instagram API Error 9007 (container not ready):**
The system already handles this with polling. If it persists, increase `POLL_INTERVAL_S` in `agents/instagram_agent.py`.

**No articles found from RSS:**
Some feeds may be temporarily down. The system will still work with available sources and fall back to local scoring if Gemini is unavailable.

**`ModuleNotFoundError`:**
Make sure you're running from the project root: `cd "e:\insta agents" && python main.py`
