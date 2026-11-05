# Cross-Posting Framework

This is a **legitimate multi-platform posting framework** for YT-DLP WebUI announcements.

## ⚠️ Important: Terms of Service

**Do NOT automate account creation.** Creating accounts programmatically violates the Terms of Service of Reddit, Twitter/X, Dev.to, Hacker News, and most other platforms. This can result in permanent IP bans and legal action.

**What this framework does:**
- Posts to platforms using **official APIs** with **manually created accounts**
- Includes rate limiting to avoid being flagged as spam
- Stores credentials securely in environment variables (never hardcoded)
- Is modular — add platforms as you obtain API access

## Setup

### 1. Create accounts manually
Create accounts on each platform manually:
- **Reddit**: reddit.com/register
- **Twitter/X**: twitter.com/i/flow/signup
- **Dev.to**: dev.to/signup
- **Hacker News**: news.ycombinator.com (no API, manual only)
- **Product Hunt**: producthunt.com/signup

### 2. Get API credentials

| Platform | Where to get credentials |
|----------|-------------------------|
| Reddit | reddit.com/prefs/apps → Create App |
| Twitter/X | developer.twitter.com → Create Project + App |
| Dev.to | dev.to/settings/api_keys |
| Hacker News | No public API (manual posting only) |
| Product Hunt | contact@producthunt.com (no public API) |

### 3. Set environment variables

```bash
# Reddit
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USERNAME="your_username"
export REDDIT_PASSWORD="your_password"

# Twitter/X
export TWITTER_API_KEY="your_api_key"
export TWITTER_API_SECRET="your_api_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"

# Dev.to
export DEVTO_API_KEY="your_devto_api_key"

# General
export CROSSPOST_USER_AGENT="yt-dlp-webui-bot/1.0"
```

### 4. Install dependencies

```bash
pip install praw tweepy requests python-dotenv
```

### 5. Run

```bash
python crosspost/main.py
```

---

## Platform Support Matrix

| Platform | API Available? | Auto-Post? | Notes |
|----------|---------------|------------|-------|
| Reddit | ✅ Yes (PRAW) | ✅ Yes | Requires app registration |
| Twitter/X | ✅ Yes (API v2) | ✅ Yes | Requires developer approval |
| Dev.to | ✅ Yes | ✅ Yes | API key in settings |
| Hacker News | ❌ No | ❌ No | Manual only |
| Product Hunt | ❌ No | ❌ No | Manual only |
| LinkedIn | ✅ Yes (limited) | ⚠️ Limited | Requires partner access |

## Rate Limits

| Platform | Rate Limit | Notes |
|----------|-----------|-------|
| Reddit | 1 request/second | Don't post more than once per minute |
| Twitter/X | 50 tweets/24h (free tier) | Very restrictive |
| Dev.to | 100 requests/day | Reasonable |
| Hacker News | N/A | Manual only |

## Adding a New Platform

1. Create an account manually
2. Get API credentials
3. Add a new class in `platforms/` following the `BasePoster` pattern
4. Add the platform to `POSTERS` dict in `main.py`
5. Add environment variables for credentials
